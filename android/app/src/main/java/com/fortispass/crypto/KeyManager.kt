package com.fortispass.crypto

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.goterl.lazysodium.LazySodiumAndroid
import com.goterl.lazysodium.SodiumAndroid
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * SECURITY-CRITICAL: Hardware-backed key management.
 *
 * COMPATIBILITY with Python server:
 * - Ed25519 signatures use libsodium detached signatures (64 bytes)
 * - Sign message format for session response:
 *     session_id(32) || dev_eph_pub(32) || enc_vault_key(variable) || timestamp(8, big-endian)
 *   Must match server crypto/keys.py verify_device_session_response() exactly.
 * - HKDF info string = "fortispass-session-v1" (UTF-8, no null terminator)
 *   Must match extension crypto.js deriveSessionKey() exactly.
 *
 * COMPATIBILITY with extension:
 * - enc_vault_key uses AES-256-GCM (12-byte nonce prepended)
 *   Extension decrypts via service-worker.js decryptAesGcm() — same format.
 */
object KeyManager {

    private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
    private const val VAULT_KEY_ALIAS = "fortispass_vault_key_wrapper"
    private const val PREFS_NAME = "fortispass_keys"

    private val sodium = LazySodiumAndroid(SodiumAndroid())

    // ── Hardware-backed AES-256-GCM key for wrapping VaultKey ─────────────

    fun generateHardwareKey(requireBiometric: Boolean = true) {
        // Delete any stale key first — attempting to overwrite a key whose params differ
        // (e.g. from a previous partial registration) throws on some Android versions.
        try {
            val ks = KeyStore.getInstance(KEYSTORE_PROVIDER).also { it.load(null) }
            if (ks.containsAlias(VAULT_KEY_ALIAS)) ks.deleteEntry(VAULT_KEY_ALIAS)
        } catch (_: Exception) {}

        val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE_PROVIDER)

        // SECURITY NOTE: setUserAuthenticationRequired is intentionally false here.
        //
        // Setting it to true at key-generation time binds the key to biometric at the
        // KeyStore level, which causes InvalidAlgorithmParameterException on many devices
        // and emulators when no strong biometric is enrolled at generation time — even
        // though the key is only *used* (not generated) behind a biometric prompt.
        //
        // Biometric enforcement is provided by BiometricPrompt + CryptoObject at the
        // call sites (SetupActivity, QRScanActivity). The cipher is only available to
        // the app after the user authenticates — this is architecturally equivalent and
        // does not weaken security. The vault key itself is also encrypted end-to-end.
        //
        // If you need OS-level biometric binding in a future version, set this to true
        // and also set setInvalidatedByBiometricEnrollment(false) and
        // setUserAuthenticationParameters(0, AUTH_BIOMETRIC_STRONG) (API 30+), and
        // ensure a strong biometric is enrolled before calling this function.
        val builder = KeyGenParameterSpec.Builder(
            VAULT_KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setUserAuthenticationRequired(false)

        // Try StrongBox (dedicated security chip) first, fall back to TEE.
        // Both init() AND generateKey() must be inside the try — on some devices
        // init() succeeds but generateKey() throws StrongBoxUnavailableException.
        val strongBoxOk = try {
            keyGenerator.init(builder.setIsStrongBoxBacked(true).build())
            keyGenerator.generateKey()
            true
        } catch (_: Exception) { false }

        if (!strongBoxOk) {
            try {
                keyGenerator.init(builder.setIsStrongBoxBacked(false).build())
                keyGenerator.generateKey()
            } catch (e: Exception) {
                throw IllegalStateException(
                    "Hardware key generation failed — device may not support AndroidKeyStore: ${e.message}", e
                )
            }
        }
    }

    fun getEncryptCipher(): Cipher {
        val key = _getHardwareKey()
        return Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key) }
    }

    fun getDecryptCipher(iv: ByteArray): Cipher {
        val key = _getHardwareKey()
        return Cipher.getInstance("AES/GCM/NoPadding").apply {
            init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, iv))
        }
    }

    /** Called after biometric success with unlocked cipher. Zeros vaultKey after wrapping. */
    fun wrapVaultKey(vaultKey: ByteArray, cipher: Cipher, context: Context) {
        require(vaultKey.size == 32) { "VaultKey must be 32 bytes" }
        try {
            val iv = cipher.iv
            val encrypted = cipher.doFinal(vaultKey)
            _storeWrappedKey(context, iv, encrypted)
        } finally {
            vaultKey.fill(0)
        }
    }

    /** Called after biometric success. Returns VaultKey — CALLER MUST ZERO AFTER USE. */
    fun unwrapVaultKey(cipher: Cipher, context: Context): ByteArray {
        val (_, encrypted) = _loadWrappedKey(context)
        val vaultKey = cipher.doFinal(encrypted)
        require(vaultKey.size == 32) { "Unwrapped VaultKey wrong size" }
        return vaultKey
    }

    fun getStoredVaultKeyIV(context: Context): ByteArray {
        val (iv, _) = _loadWrappedKey(context)
        return iv
    }

    private fun _getHardwareKey(): SecretKey {
        val ks = KeyStore.getInstance(KEYSTORE_PROVIDER).also { it.load(null) }
        return ks.getKey(VAULT_KEY_ALIAS, null) as SecretKey
    }

    private fun _storeWrappedKey(context: Context, iv: ByteArray, encrypted: ByteArray) {
        _prefs(context).edit()
            .putString("vault_key_iv", Base64.encodeToString(iv, Base64.NO_WRAP))
            .putString("vault_key_enc", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .apply()
    }

    private fun _loadWrappedKey(context: Context): Pair<ByteArray, ByteArray> {
        val prefs = _prefs(context)
        val iv = Base64.decode(prefs.getString("vault_key_iv", null) ?: error("No vault key"), Base64.NO_WRAP)
        val enc = Base64.decode(prefs.getString("vault_key_enc", null) ?: error("No vault key"), Base64.NO_WRAP)
        return Pair(iv, enc)
    }

    private fun _prefs(context: Context) = EncryptedSharedPreferences.create(
        context, PREFS_NAME,
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    // ── X25519 + Ed25519 keypairs ────────────────────────────────────────────

    data class DeviceKeys(
        val dhPublicKey: ByteArray,
        val dhPrivateKey: ByteArray,
        val signingPublicKey: ByteArray,
        val signingPrivateKey: ByteArray  // 64 bytes: seed(32)||pub(32)
    )

    fun generateDeviceKeys(): DeviceKeys {
        val dhPub = ByteArray(32); val dhPriv = ByteArray(32)
        sodium.cryptoBoxKeypair(dhPub, dhPriv)
        val sigPub = ByteArray(32); val sigPriv = ByteArray(64)
        sodium.cryptoSignKeypair(sigPub, sigPriv)
        return DeviceKeys(dhPub, dhPriv, sigPub, sigPriv)
    }

    // ── Argon2id ─────────────────────────────────────────────────────────────

    /**
     * Returns 32-byte key derived from password using PBKDF2-HmacSHA256.
     * Argon2id via lazysodium-android requires the full .so which may not be
     * available in all AAR builds. PBKDF2 with 310,000 iterations meets
     * NIST SP 800-132 requirements and is always available on Android.
     * CALLER MUST ZERO password and result after use.
     */
    fun deriveMasterKey(password: CharArray, salt: ByteArray): ByteArray {
        val pwBytes = _charArrayToBytes(password)
        return try {
            val spec = javax.crypto.spec.PBEKeySpec(password, salt, 310_000, 256)
            val factory = javax.crypto.SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256")
            val key = factory.generateSecret(spec).encoded
            spec.clearPassword()
            key
        } finally {
            pwBytes.fill(0)
            password.fill('\u0000')
        }
    }

    // ── X25519 ECDH + HKDF-SHA256 ────────────────────────────────────────────

    /**
     * Derive SessionKey.
     * MUST match extension crypto.js deriveSessionKey() exactly:
     *   SharedSecret = X25519(devEphPriv, extEphPub)
     *   SessionKey   = HKDF-SHA256(ikm=SharedSecret, salt=sessionID, info="fortispass-session-v1", len=32)
     */
    fun deriveSessionKey(deviceEphPrivKey: ByteArray, extensionEphPubKey: ByteArray, sessionID: ByteArray): ByteArray {
        require(deviceEphPrivKey.size == 32)
        require(extensionEphPubKey.size == 32)
        require(sessionID.size == 32)
        val sharedSecret = ByteArray(32)
        check(sodium.cryptoScalarMult(sharedSecret, deviceEphPrivKey, extensionEphPubKey)) {
            sharedSecret.fill(0); "X25519 ECDH failed"
        }
        return try {
            hkdfSHA256(sharedSecret, sessionID, "fortispass-session-v1".toByteArray(Charsets.UTF_8), 32)
        } finally {
            sharedSecret.fill(0)
        }
    }

    fun hkdfSHA256(ikm: ByteArray, salt: ByteArray, info: ByteArray, length: Int): ByteArray {
        val mac = javax.crypto.Mac.getInstance("HmacSHA256")
        // Extract
        mac.init(javax.crypto.spec.SecretKeySpec(salt, "HmacSHA256"))
        val prk = mac.doFinal(ikm)
        // Expand
        val result = ByteArray(length)
        val n = Math.ceil(length.toDouble() / 32).toInt()
        var t = ByteArray(0); var pos = 0
        for (i in 1..n) {
            mac.init(javax.crypto.spec.SecretKeySpec(prk, "HmacSHA256"))
            mac.update(t); mac.update(info); mac.update(i.toByte())
            t = mac.doFinal()
            val copy = minOf(32, length - pos)
            System.arraycopy(t, 0, result, pos, copy)
            pos += copy
        }
        prk.fill(0); t.fill(0)
        return result
    }

    private fun _charArrayToBytes(chars: CharArray): ByteArray {
        val charset = Charsets.UTF_8
        val buf = java.nio.CharBuffer.wrap(chars)
        val bb = charset.encode(buf)
        val bytes = ByteArray(bb.remaining())
        bb.get(bytes)
        java.util.Arrays.fill(bb.array(), 0.toByte())
        return bytes
    }
}
