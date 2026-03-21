package com.fortispass.ui.setup

import android.content.Intent
import android.os.Bundle
import android.util.Base64
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.fortispass.R
import com.fortispass.crypto.CryptoEngine
import com.fortispass.crypto.KeyManager
import com.fortispass.ui.BaseActivity
import com.fortispass.ui.MainActivity
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/**
 * Device B — receives an fp_invite QR payload (via Intent extra "invite_payload"),
 * accepts the invite on the server, polls for the encrypted vault key, then decrypts
 * it using ECDH and registers as a device on the same account.
 *
 * Launched from QRScanActivity when qr["type"] == "fp_invite".
 */
class JoinVaultActivity : BaseActivity() {

    private lateinit var tvStatus: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_join_vault)

        tvStatus = findViewById(R.id.tv_status)
        findViewById<MaterialButton>(R.id.btn_back).setOnClickListener { finish() }

        val payload = intent.getStringExtra("invite_payload")
            ?: run { setStatus("No invite payload"); return }

        processInvite(payload)
    }

    private fun processInvite(rawPayload: String) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val qr = JSONObject(rawPayload)
                val relayUrl     = qr.getString("relay").trimEnd('/')
                val token        = qr.getString("token")
                val inviterDhPub = qr.getString("pub")  // Device A's X25519 pub, base64url

                // Generate Device B's keys
                val deviceKeys = KeyManager.generateDeviceKeys()
                val deviceName = android.os.Build.MODEL

                val bDhPubB64  = Base64.encodeToString(deviceKeys.dhPublicKey,      Base64.URL_SAFE or Base64.NO_WRAP)
                val bSignB64   = Base64.encodeToString(deviceKeys.signingPublicKey, Base64.URL_SAFE or Base64.NO_WRAP)

                withContext(Dispatchers.Main) { setStatus(getString(R.string.recovery_login_fetching)) }

                // POST /invite/accept
                val acceptBody = JSONObject().apply {
                    put("token",           token)
                    put("joiner_dh_pub",   bDhPubB64)
                    put("joiner_sign_pub", bSignB64)
                    put("device_name",     deviceName)
                }.toString()

                val acceptResp = post("$relayUrl/api/v1/invite/accept", acceptBody)

                when (acceptResp.optString("status")) {
                    "at_limit" -> {
                        val devicesArr = acceptResp.getJSONArray("devices")
                        val devices = (0 until devicesArr.length()).map { devicesArr.getJSONObject(it) }
                        withContext(Dispatchers.Main) {
                            showKickDialog(relayUrl, token, deviceKeys, deviceName, devices)
                        }
                        return@launch
                    }
                    "accepted" -> {
                        // Good — proceed to poll for key
                        pollForKey(relayUrl, token, deviceKeys, inviterDhPub)
                    }
                    else -> throw Exception("Unexpected status: ${acceptResp.optString("status")}")
                }

            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    setStatus(getString(R.string.add_device_error, e.message ?: "Unknown"))
                }
            }
        }
    }

    private fun showKickDialog(
        relayUrl: String, token: String,
        deviceKeys: KeyManager.DeviceKeys,
        deviceName: String,
        devices: List<JSONObject>
    ) {
        val labels = devices.map { d ->
            val name = d.optString("name", "Unknown")
            val date = d.optString("created_at", "").take(10)
            getString(R.string.kick_device_added_on, date).let { "$name  ($it)" }
        }.toTypedArray()

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.kick_device_title))
            .setMessage(getString(R.string.kick_device_message))
            .setItems(labels) { _, idx ->
                val kickId = devices[idx].getString("id")
                lifecycleScope.launch(Dispatchers.IO) {
                    try {
                        val bDhPubB64  = Base64.encodeToString(deviceKeys.dhPublicKey,      Base64.URL_SAFE or Base64.NO_WRAP)
                        val bSignB64   = Base64.encodeToString(deviceKeys.signingPublicKey, Base64.URL_SAFE or Base64.NO_WRAP)

                        val body = JSONObject().apply {
                            put("token",           token)
                            put("joiner_dh_pub",   bDhPubB64)
                            put("joiner_sign_pub", bSignB64)
                            put("device_name",     deviceName)
                            put("kick_device_id",  kickId)
                        }.toString()

                        post("$relayUrl/api/v1/invite/accept", body)

                        // Get inviter_dh_pub from status
                        val statusResp = get("$relayUrl/api/v1/invite/$token/status")
                        val inviterPub = statusResp.optString("inviting_dh_pub", "")
                            .ifEmpty { throw Exception("Could not get inviter DH pub") }

                        pollForKey(relayUrl, token, deviceKeys, inviterPub)
                    } catch (e: Exception) {
                        withContext(Dispatchers.Main) {
                            setStatus(getString(R.string.add_device_error, e.message ?: ""))
                        }
                    }
                }
            }
            .setNegativeButton(getString(R.string.cancel)) { _, _ -> finish() }
            .show()
    }

    private suspend fun pollForKey(
        relayUrl: String, token: String,
        deviceKeys: KeyManager.DeviceKeys,
        inviterDhPubB64: String
    ) {
        withContext(Dispatchers.Main) { setStatus(getString(R.string.add_device_waiting)) }

        try {
            // Poll GET /invite/{token}/status (no auth — Device B has no token yet)
            var encVaultKeyB64: String? = null
            var attempts = 0
            while (attempts < 60 && encVaultKeyB64 == null) {
                delay(3_000)
                attempts++
                val resp = try { get("$relayUrl/api/v1/invite/$token/status") } catch (_: Exception) { continue }
                if (resp.optString("state") == "delivered") {
                    encVaultKeyB64 = resp.optString("encrypted_vault_key").takeIf { it.isNotEmpty() }
                }
            }

            val encKeyB64 = encVaultKeyB64 ?: throw Exception("Vault key not delivered in time")

            withContext(Dispatchers.Main) { setStatus(getString(R.string.recovery_login_decrypting)) }

            // ECDH: Device B priv × Device A pub
            val inviterDhPubBytes = urlsafeB64Decode(inviterDhPubB64)
            val sharedSecret = ByteArray(32)
            val sodium = com.goterl.lazysodium.LazySodiumAndroid(com.goterl.lazysodium.SodiumAndroid())
            check(sodium.cryptoScalarMult(sharedSecret, deviceKeys.dhPrivateKey, inviterDhPubBytes)) {
                "X25519 ECDH failed"
            }

            val wrapKey = KeyManager.hkdfSHA256(
                sharedSecret, "fp-invite-v1".toByteArray(), ByteArray(0), 32
            )
            sharedSecret.fill(0)

            val encKeyBytes = Base64.decode(encKeyB64, Base64.DEFAULT)
            val vaultKey = CryptoEngine.decryptVault(encKeyBytes, wrapKey)
            wrapKey.fill(0)

            // Complete registration
            withContext(Dispatchers.Main) { setStatus(getString(R.string.recovery_login_registering)) }

            val bDhPubB64  = Base64.encodeToString(deviceKeys.dhPublicKey,      Base64.URL_SAFE or Base64.NO_WRAP)
            val bSignB64   = Base64.encodeToString(deviceKeys.signingPublicKey, Base64.URL_SAFE or Base64.NO_WRAP)

            val completeBody = JSONObject().apply {
                put("token",       token)
                put("device_name", android.os.Build.MODEL)
                put("dh_pub",      bDhPubB64)
                put("signing_pub", bSignB64)
            }.toString()

            val completeResp = post("$relayUrl/api/v1/invite/complete", completeBody)

            val authToken    = completeResp.getString("access_token")
            val deviceId     = completeResp.getString("device_id")
            val serverPubKey = completeResp.getString("server_pub_key")
            val mnemonicOk   = completeResp.optBoolean("mnemonic_confirmed", false)
            val vaultBlobB64 = completeResp.optString("encrypted_vault_blob").takeIf { it.isNotEmpty() }

            // Wrap vault key in hardware Keystore
            KeyManager.generateHardwareKey()
            val encCipher = KeyManager.getEncryptCipher()
            KeyManager.wrapVaultKey(vaultKey.copyOf(), encCipher, this@JoinVaultActivity)
            vaultKey.fill(0)

            // Store device credentials
            val encPrefs = EncryptedSharedPreferences.create(
                this@JoinVaultActivity, "fortispass_device",
                MasterKey.Builder(this@JoinVaultActivity).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            encPrefs.edit()
                .putString("relay_url",        relayUrl)
                .putString("auth_token",        authToken)
                .putString("device_id",         deviceId)
                .putString("server_pub_key",    serverPubKey)
                .putString("signing_priv_key",  Base64.encodeToString(deviceKeys.signingPrivateKey, Base64.NO_WRAP))
                .apply()

            // Pin server fingerprint
            com.fortispass.network.ServerTrust.pinFromMigration(this@JoinVaultActivity, relayUrl, serverPubKey)

            // If server included vault blob, store it in vault_blobs prefs for extension access
            // (the vault is already on the server under the account — extension fetches it via auth token)

            withContext(Dispatchers.Main) {
                Toast.makeText(this@JoinVaultActivity,
                    getString(R.string.add_device_done), Toast.LENGTH_LONG).show()
                startActivity(Intent(this@JoinVaultActivity, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
                finish()
            }

        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                setStatus(getString(R.string.add_device_error, e.message ?: "Unknown"))
            }
        }
    }

    // ── Network ─────────────────────────────────────────────────────────────────

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

    private fun get(url: String, token: String? = null): JSONObject {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            if (token != null) setRequestProperty("Authorization", "Bearer $token")
            connectTimeout = 10_000; readTimeout = 10_000
        }
        val code = conn.responseCode
        val text = if (code in 200..299)
            conn.inputStream.bufferedReader().readText()
        else conn.errorStream?.bufferedReader()?.readText() ?: ""
        if (code !in 200..299) throw Exception("HTTP $code: $text")
        return if (text.isBlank()) JSONObject() else JSONObject(text)
    }

    private fun urlsafeB64Decode(s: String): ByteArray {
        val std = s.replace('-', '+').replace('_', '/')
        val padded = std + "=".repeat((4 - std.length % 4) % 4)
        return Base64.decode(padded, Base64.DEFAULT)
    }

    private fun setStatus(msg: String) { tvStatus.text = msg }
}
