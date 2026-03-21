package com.fortispass.ui.settings

import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.util.Base64
import android.widget.ImageView
import android.widget.TextView
import androidx.lifecycle.lifecycleScope
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.fortispass.R
import com.fortispass.crypto.CryptoEngine
import com.fortispass.crypto.KeyManager
import com.fortispass.ui.BaseActivity
import com.google.android.material.button.MaterialButton
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import javax.crypto.AEADBadTagException

/**
 * Device A — generates an invite QR code, polls the relay until Device B
 * has accepted, then performs ECDH to encrypt the vault key for Device B.
 *
 * QR payload:
 *   {"type":"fp_invite","v":1,"relay":"...","token":"...","pub":"<A_dh_pub_b64url>"}
 */
class AddDeviceActivity : BaseActivity() {

    private lateinit var ivQr:     ImageView
    private lateinit var tvStatus: TextView

    private var relayUrl:  String = ""
    private var authToken: String = ""
    private var inviteToken: String = ""
    private var pollJob: kotlinx.coroutines.Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_add_device)

        ivQr     = findViewById(R.id.iv_qr)
        tvStatus = findViewById(R.id.tv_status)

        findViewById<MaterialButton>(R.id.btn_back).setOnClickListener {
            pollJob?.cancel()
            finish()
        }

        loadCredentialsAndStart()
    }

    override fun onDestroy() {
        super.onDestroy()
        pollJob?.cancel()
    }

    private fun loadCredentialsAndStart() {
        val prefs = try {
            EncryptedSharedPreferences.create(
                this, "fortispass_device",
                MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) { setStatus("Cannot read credentials: ${e.message}"); return }

        relayUrl  = prefs.getString("relay_url",  null) ?: run { setStatus("Not registered"); return }
        authToken = prefs.getString("auth_token", null) ?: run { setStatus("Not registered"); return }

        // We need the vault key to encrypt for Device B — require biometric
        requireBiometricWithCipherInternal { cipher ->
            val vaultKey = try {
                KeyManager.unwrapVaultKey(cipher, this)
            } catch (e: Exception) {
                setStatus("Cannot unlock vault key: ${e.message}"); return@requireBiometricWithCipherInternal
            }
            createInviteAndShow(vaultKey)
        }
    }

    private fun createInviteAndShow(vaultKey: ByteArray) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // POST /invite/create
                val resp = post("$relayUrl/api/v1/invite/create", "{}", authToken)
                val token     = resp.getString("token")
                val invDhPub  = resp.getString("inviting_dh_pub")  // Device A's DH pub from server
                inviteToken   = token

                val qrPayload = JSONObject().apply {
                    put("type",  "fp_invite")
                    put("v",     1)
                    put("relay", relayUrl)
                    put("token", token)
                    put("pub",   invDhPub)
                }.toString()

                val qrBitmap = generateQR(qrPayload, 600)
                withContext(Dispatchers.Main) {
                    ivQr.setImageBitmap(qrBitmap)
                    setStatus(getString(R.string.add_device_waiting))
                }

                // Poll until accepted (state == "accepted")
                pollJob = launch { pollForAccepted(vaultKey, token) }

            } catch (e: Exception) {
                vaultKey.fill(0)
                withContext(Dispatchers.Main) {
                    setStatus(getString(R.string.add_device_error, e.message ?: ""))
                }
            }
        }
    }

    private suspend fun pollForAccepted(vaultKey: ByteArray, token: String) {
        try {
            var attempts = 0
            while (attempts < 60) {
                delay(5_000)
                attempts++

                val resp = try {
                    get("$relayUrl/api/v1/invite/$token/status", authToken)
                } catch (_: Exception) { continue }

                val state = resp.optString("state")
                if (state == "accepted") {
                    val joinerDhPubB64 = resp.optString("joiner_dh_pub")
                        .takeIf { it.isNotEmpty() } ?: continue

                    withContext(Dispatchers.Main) {
                        setStatus(getString(R.string.add_device_accepted))
                    }

                    deliverVaultKey(vaultKey, token, joinerDhPubB64)
                    return
                }
                if (state == "consumed") return
            }
            // Timed out
            vaultKey.fill(0)
            withContext(Dispatchers.Main) {
                setStatus(getString(R.string.add_device_expired))
            }
        } catch (e: Exception) {
            vaultKey.fill(0)
            withContext(Dispatchers.Main) {
                setStatus(getString(R.string.add_device_error, e.message ?: ""))
            }
        }
    }

    private suspend fun deliverVaultKey(vaultKey: ByteArray, token: String, joinerDhPubB64: String) {
        try {
            val joinerDhPub = Base64.decode(
                joinerDhPubB64.padEnd(joinerDhPubB64.length + (4 - joinerDhPubB64.length % 4) % 4, '=')
                    .replace('-', '+').replace('_', '/'), Base64.DEFAULT
            )
            // ECDH: use Device A's DH private key + Device B's DH public key
            val prefs = EncryptedSharedPreferences.create(
                this@AddDeviceActivity, "fortispass_keys",
                MasterKey.Builder(this@AddDeviceActivity).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            val aDhPrivB64 = prefs.getString("dh_priv_key", null)
                ?: throw Exception("DH private key not found")
            val aDhPriv = Base64.decode(aDhPrivB64, Base64.NO_WRAP)

            // Shared secret via X25519
            val sharedSecret = ByteArray(32)
            val sodium = com.goterl.lazysodium.LazySodiumAndroid(com.goterl.lazysodium.SodiumAndroid())
            check(sodium.cryptoScalarMult(sharedSecret, aDhPriv, joinerDhPub)) {
                "X25519 ECDH failed"
            }
            aDhPriv.fill(0)

            // Derive wrap key: HKDF(sharedSecret, salt="fp-invite-v1", info="", len=32)
            val wrapKey = KeyManager.hkdfSHA256(
                sharedSecret, "fp-invite-v1".toByteArray(), ByteArray(0), 32
            )
            sharedSecret.fill(0)

            // AES-GCM encrypt vault key with wrap key
            val encVaultKey = CryptoEngine.encryptVault(vaultKey, wrapKey)
            wrapKey.fill(0)
            vaultKey.fill(0)

            val encB64 = Base64.encodeToString(encVaultKey, Base64.NO_WRAP)
            val body = JSONObject().apply {
                put("token", token)
                put("encrypted_vault_key", encB64)
            }.toString()

            post("$relayUrl/api/v1/invite/deliver", body, authToken)

            withContext(Dispatchers.Main) {
                setStatus(getString(R.string.add_device_done))
            }
        } catch (e: Exception) {
            vaultKey.fill(0)
            withContext(Dispatchers.Main) {
                setStatus(getString(R.string.add_device_error, e.message ?: ""))
            }
        }
    }

    // ── Biometric ─────────────────────────────────────────────────────────────

    private fun requireBiometricWithCipherInternal(onSuccess: (javax.crypto.Cipher) -> Unit) {
        val cipher = try {
            KeyManager.getDecryptCipher(KeyManager.getStoredVaultKeyIV(this))
        } catch (e: Exception) { setStatus("Cannot init cipher: ${e.message}"); return }

        val prompt = androidx.biometric.BiometricPrompt(this,
            androidx.core.content.ContextCompat.getMainExecutor(this),
            object : androidx.biometric.BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(r: androidx.biometric.BiometricPrompt.AuthenticationResult) {
                    r.cryptoObject?.cipher?.let { onSuccess(it) } ?: setStatus("Biometric cipher unavailable")
                }
                override fun onAuthenticationError(code: Int, msg: CharSequence) {
                    if (code != androidx.biometric.BiometricPrompt.ERROR_NEGATIVE_BUTTON &&
                        code != androidx.biometric.BiometricPrompt.ERROR_USER_CANCELED)
                        setStatus("Biometric error: $msg")
                    else finish()
                }
                override fun onAuthenticationFailed() { setStatus(getString(R.string.biometric_not_recognised)) }
            })
        val info = androidx.biometric.BiometricPrompt.PromptInfo.Builder()
            .setTitle(getString(R.string.biometric_title))
            .setSubtitle(getString(R.string.add_device_title))
            .setAllowedAuthenticators(androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText(getString(R.string.cancel))
            .build()
        prompt.authenticate(info, androidx.biometric.BiometricPrompt.CryptoObject(cipher))
    }

    // ── Networking ─────────────────────────────────────────────────────────────

    private fun post(url: String, body: String, token: String? = null): JSONObject {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            setRequestProperty("Content-Type", "application/json")
            if (token != null) setRequestProperty("Authorization", "Bearer $token")
            doOutput = true; connectTimeout = 10_000; readTimeout = 10_000
        }
        conn.outputStream.use { it.write(body.toByteArray()) }
        val code = conn.responseCode
        val text = if (code in 200..299)
            conn.inputStream.bufferedReader().readText()
        else conn.errorStream?.bufferedReader()?.readText() ?: ""
        if (code !in 200..299) throw Exception("HTTP $code: $text")
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private fun get(url: String, token: String): JSONObject {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            setRequestProperty("Authorization", "Bearer $token")
            connectTimeout = 10_000; readTimeout = 10_000
        }
        val code = conn.responseCode
        val text = if (code in 200..299)
            conn.inputStream.bufferedReader().readText()
        else conn.errorStream?.bufferedReader()?.readText() ?: ""
        if (code !in 200..299) throw Exception("HTTP $code: $text")
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    // ── Helpers ────────────────────────────────────────────────────────────────

    private fun setStatus(msg: String) {
        tvStatus.text = msg
    }

    private fun generateQR(content: String, size: Int): Bitmap {
        val bits = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size)
        val bmp  = Bitmap.createBitmap(size, size, Bitmap.Config.RGB_565)
        for (x in 0 until size) for (y in 0 until size)
            bmp.setPixel(x, y, if (bits[x, y]) Color.BLACK else Color.WHITE)
        return bmp
    }
}
