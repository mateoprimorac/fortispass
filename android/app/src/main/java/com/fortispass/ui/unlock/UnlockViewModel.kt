package com.fortispass.ui.unlock

import android.app.Application
import android.util.Base64
import androidx.lifecycle.AndroidViewModel
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.fortispass.network.RelayClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

class UnlockViewModel(app: Application) : AndroidViewModel(app) {

    private val prefs = EncryptedSharedPreferences.create(
        app, "fortispass_device",
        MasterKey.Builder(app).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    /** Pinned server Ed25519 pub key — set at account registration. */
    fun getServerPublicKey(): ByteArray {
        val b64 = prefs.getString("server_pub_key", null)
            ?: throw IllegalStateException("Server public key not pinned")
        return Base64.decode(b64, Base64.NO_WRAP)
    }

    /** Base64-encoded server pub key for comparison with ServerTrust pin. */
    fun getServerPublicKey64(): String =
        prefs.getString("server_pub_key", null)
            ?: throw IllegalStateException("Server public key not pinned")

    /** Device Ed25519 signing key (64 bytes). Stored encrypted. */
    fun getDeviceSigningKey(): ByteArray {
        val b64 = prefs.getString("signing_priv_key", null)
            ?: throw IllegalStateException("Device signing key not found")
        return Base64.decode(b64, Base64.NO_WRAP)
    }

    fun getDeviceID(): String =
        prefs.getString("device_id", null) ?: throw IllegalStateException("Device ID not found")

    fun getAuthToken(): String =
        prefs.getString("auth_token", null) ?: throw IllegalStateException("Auth token not found")

    /** True if the stored access token is expired or expires within the next 60 seconds. */
    fun isTokenExpiredOrNearExpiry(): Boolean {
        val token = prefs.getString("auth_token", null) ?: return true
        return try {
            // JWT is header.payload.sig — decode payload (Base64url, no padding)
            val parts = token.split(".")
            if (parts.size != 3) return true
            val payload = JSONObject(String(Base64.decode(parts[1], Base64.URL_SAFE or Base64.NO_WRAP)))
            val exp = payload.optLong("exp", 0L)
            exp < (System.currentTimeMillis() / 1000) + 60
        } catch (_: Exception) { true }
    }

    /**
     * Returns a valid auth token, renewing it transparently if expired.
     * Saves the new token back to EncryptedSharedPreferences.
     */
    suspend fun getOrRenewAuthToken(): String = withContext(Dispatchers.IO) {
        if (!isTokenExpiredOrNearExpiry()) return@withContext getAuthToken()

        val oldToken   = getAuthToken()
        val deviceId   = getDeviceID()
        val signingKey = getDeviceSigningKey()
        val relayUrl   = prefs.getString("relay_url", null)
            ?: throw IllegalStateException("Relay URL not found")

        val newToken = RelayClient.renewToken(relayUrl, oldToken, deviceId, signingKey)
        prefs.edit().putString("auth_token", newToken).apply()
        newToken
    }
}
