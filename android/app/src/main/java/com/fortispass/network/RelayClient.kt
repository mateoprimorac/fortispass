package com.fortispass.network

import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object RelayClient {

    data class RegistrationResult(
        val authToken: String,
        val deviceId: String,
        val serverPubKey: String
    )

    /** Register a new device — no email or password. Keys are the identity. */
    suspend fun registerDevice(
        relayUrl: String,
        deviceName: String,
        dhPubKey: ByteArray,
        sigPubKey: ByteArray,
        initialVault: ByteArray,
        vaultLookupHash: String? = null,
    ): RegistrationResult = withContext(Dispatchers.IO) {
        val b64 = { b: ByteArray -> Base64.encodeToString(b, Base64.URL_SAFE or Base64.NO_WRAP) }

        val body = JSONObject().apply {
            put("device_name", deviceName)
            put("device", JSONObject().apply {
                put("name",            deviceName)
                put("dh_public_key",   b64(dhPubKey))
                put("signing_pub_key", b64(sigPubKey))
            })
            put("initial_vault", b64(initialVault))
            if (vaultLookupHash != null) put("vault_lookup_hash", vaultLookupHash)
        }.toString()

        val resp = post("$relayUrl/api/v1/auth/register", body, token = null)
        RegistrationResult(
            authToken    = resp.getString("access_token"),
            deviceId     = resp.getString("device_id"),
            serverPubKey = resp.optString("server_pub_key", "")
        )
    }

    /** Notify relay that QR was scanned and biometric prompt is showing. */
    suspend fun ackSession(
        relayUrl: String,
        sessionID: String
    ) = withContext(Dispatchers.IO) {
        // No auth token needed — session_id in path is the credential
        post("$relayUrl/api/v1/session/ack/$sessionID", "{}", token = null)
    }

    /** Cancel a session (biometric failed/cancelled). Relay notifies extension. */
    suspend fun cancelSession(
        relayUrl: String,
        sessionID: String,
        reason: String = "biometric_failed"
    ) = withContext(Dispatchers.IO) {
        val conn = (java.net.URL("$relayUrl/api/v1/session/$sessionID?reason=$reason").openConnection() as java.net.HttpURLConnection).apply {
            requestMethod = "DELETE"
            connectTimeout = 10_000
            readTimeout = 10_000
        }
        conn.responseCode // fire and forget
    }

    /** Send encrypted vault key to relay after biometric auth. */
    suspend fun respondToSession(
        relayUrl: String,
        sessionID: String,
        devEphPub: ByteArray,
        encVaultKey: ByteArray,
        sig: ByteArray,
        deviceID: String,
        timestamp: Long,
        authToken: String
    ) = withContext(Dispatchers.IO) {
        val b64 = { b: ByteArray -> Base64.encodeToString(b, Base64.URL_SAFE or Base64.NO_WRAP) }
        val body = JSONObject().apply {
            put("session_id",    sessionID)
            put("dev_eph_pub",   b64(devEphPub))
            put("enc_vault_key", b64(encVaultKey))
            put("sig",           b64(sig))
            put("device_id",     deviceID)
            put("timestamp",     timestamp)
        }.toString()
        post("$relayUrl/api/v1/session/respond", body, authToken)
    }

    /**
     * Renew an expired access token using the device's Ed25519 signing key.
     * Returns the new token string.
     */
    suspend fun renewToken(
        relayUrl: String,
        expiredToken: String,
        deviceId: String,
        signingKey: ByteArray
    ): String = withContext(Dispatchers.IO) {
        // Sign the device_id bytes to prove key possession
        val sod = com.goterl.lazysodium.LazySodiumAndroid(com.goterl.lazysodium.SodiumAndroid())
        val msg = deviceId.toByteArray(Charsets.UTF_8)
        val sig = ByteArray(64)
        sod.cryptoSignDetached(sig, msg, msg.size.toLong(), signingKey)
        val b64 = { b: ByteArray -> android.util.Base64.encodeToString(b, android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP) }
        val body = org.json.JSONObject().apply {
            put("token",     expiredToken)
            put("device_id", deviceId)
            put("sig",       b64(sig))
        }.toString()
        val resp = post("$relayUrl/api/v1/auth/renew", body, token = null)
        resp.getString("access_token")
    }

    private fun post(url: String, body: String, token: String?): JSONObject {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            setRequestProperty("Content-Type", "application/json")
            if (token != null) setRequestProperty("Authorization", "Bearer $token")
            doOutput = true
            connectTimeout = 15_000
            readTimeout    = 15_000
        }
        OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }
        val code = conn.responseCode
        if (code !in 200..299) {
            val err = runCatching { conn.errorStream?.bufferedReader()?.readText() }.getOrNull() ?: ""
            throw Exception("HTTP $code: $err")
        }
        return JSONObject(conn.inputStream.bufferedReader().readText())
    }
}
