package com.fortispass.crypto

import com.goterl.lazysodium.LazySodiumAndroid
import com.goterl.lazysodium.SodiumAndroid
import com.goterl.lazysodium.utils.Key
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Crypto operations for fortispass.
 *
 * Encryption uses AES-256-GCM via Android's built-in JCE provider.
 * This avoids all lazysodium JVM wrapper type-signature issues while
 * remaining interoperable with the extension (which uses XChaCha20-Poly1305).
 *
 * WIRE FORMAT — matches extension service-worker.js decryptAesGcm():
 *   nonce(12 bytes) || ciphertext+tag(16 bytes)
 *   AES-256-GCM, 12-byte nonce, 128-bit tag — both sides identical.
 *
 * Ed25519 sign/verify still uses lazysodium — only the AEAD is replaced.
 */
object CryptoEngine {

    private val sodium = LazySodiumAndroid(SodiumAndroid())

    // ── Vault encryption (AES-256-GCM) ───────────────────────────────────────

    fun encryptVault(plaintext: ByteArray, vaultKey: ByteArray): ByteArray =
        aesGcmEncrypt(plaintext, vaultKey)

    fun decryptVault(blob: ByteArray, vaultKey: ByteArray): ByteArray =
        aesGcmDecrypt(blob, vaultKey)

    fun encryptForSession(plaintext: ByteArray, sessionKey: ByteArray): ByteArray =
        aesGcmEncrypt(plaintext, sessionKey)

    fun decryptFromSession(blob: ByteArray, sessionKey: ByteArray): ByteArray =
        aesGcmDecrypt(blob, sessionKey)

    // ── AES-256-GCM ──────────────────────────────────────────────────────────

    private fun aesGcmEncrypt(plaintext: ByteArray, key: ByteArray): ByteArray {
        require(key.size == 32) { "Key must be 32 bytes" }
        val nonce = ByteArray(12).also { SecureRandom().nextBytes(it) }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        val ciphertext = cipher.doFinal(plaintext)  // includes 16-byte tag appended by JCE
        return nonce + ciphertext
    }

    private fun aesGcmDecrypt(blob: ByteArray, key: ByteArray): ByteArray {
        require(key.size == 32) { "Key must be 32 bytes" }
        require(blob.size >= 28) { "Blob too short (min 12 nonce + 16 tag)" }
        val nonce      = blob.copyOf(12)
        val ciphertext = blob.copyOfRange(12, blob.size)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        return try {
            cipher.doFinal(ciphertext)
        } catch (e: javax.crypto.AEADBadTagException) {
            throw SecurityException("Decryption auth tag mismatch")
        }
    }

    // ── Ed25519 sign / verify (lazysodium) ───────────────────────────────────

    fun signSessionResponse(
        sessionID: ByteArray,
        devEphPub: ByteArray,
        encVaultKey: ByteArray,
        timestamp: Long,
        signingKey: ByteArray
    ): ByteArray {
        val tsBuf = ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN).putLong(timestamp).array()
        return sign(sessionID + devEphPub + encVaultKey + tsBuf, signingKey)
    }

    fun sign(message: ByteArray, signingKey: ByteArray): ByteArray {
        require(signingKey.size == 64) { "Ed25519 signing key must be 64 bytes" }
        val sig = ByteArray(64)
        // Confirmed signature from compiler error:
        // cryptoSignDetached(sig: ByteArray, msg: ByteArray, msgLen: Long, sk: ByteArray): Boolean
        sodium.cryptoSignDetached(sig, message, message.size.toLong(), signingKey)
        return sig
    }

    fun verify(message: ByteArray, sig: ByteArray, pubKey: ByteArray): Boolean {
        require(pubKey.size == 32) { "Ed25519 pub key must be 32 bytes" }
        require(sig.size == 64)    { "Ed25519 sig must be 64 bytes" }
        // Confirmed signature from compiler error:
        // cryptoSignVerifyDetached(sig: ByteArray, msg: ByteArray, msgLen: Int, pk: ByteArray): Boolean
        return sodium.cryptoSignVerifyDetached(sig, message, message.size, pubKey)
    }
}
