package com.fortispass.network

import android.content.Context
import android.util.Base64
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * Trust-On-First-Use (TOFU) server key pinning.
 *
 * How it works:
 *  1. First time the user enters a relay URL, we fetch the server's Ed25519 public key
 *     from GET /api/v1/server/pubkey and show the fingerprint to the user.
 *  2. The user confirms ("Yes, this is my server") — the key is pinned in
 *     EncryptedSharedPreferences.
 *  3. Every subsequent QR scan verifies the session signature against the pinned key.
 *     If the key changes, the app blocks the unlock and warns the user.
 *
 * This is the same model SSH uses. No hardcoded keys required — works for any
 * self-hosted server without changes to the app.
 */
object ServerTrust {

    private const val TAG = "ServerTrust"

    data class ServerIdentity(
        val pubKeyBase64: String,     // base64 Ed25519 public key (32 bytes)
        val fingerprint: String,      // "AA:BB:CC:..." SHA-256 of raw key bytes
        val relayUrl: String
    ) {
        val pubKeyBytes: ByteArray
            get() = Base64.decode(pubKeyBase64, Base64.DEFAULT)
    }

    /**
     * Fetch the server's public key from the relay.
     * Does NOT pin it — call [pin] after user confirms.
     */
    suspend fun fetch(relayUrl: String): ServerIdentity = withContext(Dispatchers.IO) {
        val url = relayUrl.trimEnd('/') + "/api/v1/server/pubkey"
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10_000
            readTimeout    = 10_000
        }
        val code = conn.responseCode
        if (code !in 200..299) {
            throw Exception("Server returned HTTP $code fetching public key")
        }
        val body = JSONObject(conn.inputStream.bufferedReader().readText())
        val pub64 = body.getString("ed25519_pub")
        val fp    = body.optString("fingerprint", computeFingerprint(pub64))
        ServerIdentity(pub64, fp, relayUrl.trimEnd('/'))
    }

    /**
     * Pin the server identity after the user has confirmed it.
     * Overwrites any existing pin for this relay URL.
     */
    fun pin(context: Context, identity: ServerIdentity) {
        prefs(context).edit()
            .putString(prefKey(identity.relayUrl, "pub"),         identity.pubKeyBase64)
            .putString(prefKey(identity.relayUrl, "fingerprint"), identity.fingerprint)
            .putLong  (prefKey(identity.relayUrl, "pinned_at"),   System.currentTimeMillis())
            .apply()
        Log.i(TAG, "Pinned key for ${identity.relayUrl} fp=${identity.fingerprint}")
    }

    /**
     * Return the pinned identity for a relay URL, or null if not pinned.
     */
    fun getPinned(context: Context, relayUrl: String): ServerIdentity? {
        val p = prefs(context)
        val pub = p.getString(prefKey(relayUrl, "pub"), null) ?: return null
        val fp  = p.getString(prefKey(relayUrl, "fingerprint"), null) ?: return null
        return ServerIdentity(pub, fp, relayUrl.trimEnd('/'))
    }

    /**
     * Verify a fetched identity against the stored pin.
     *
     * Returns one of:
     *  - Trusted    → keys match, proceed
     *  - NotPinned  → no pin stored, caller should fetch + prompt
     *  - Mismatch   → key changed — BLOCK and warn user
     */
    sealed class VerifyResult {
        object Trusted   : VerifyResult()
        object NotPinned : VerifyResult()
        data class Mismatch(val pinnedFp: String, val seenFp: String) : VerifyResult()
    }

    fun verify(context: Context, relayUrl: String, seenPubBase64: String): VerifyResult {
        val pinned = getPinned(context, relayUrl) ?: return VerifyResult.NotPinned
        return if (pinned.pubKeyBase64 == seenPubBase64) {
            VerifyResult.Trusted
        } else {
            val seenFp = computeFingerprint(seenPubBase64)
            VerifyResult.Mismatch(pinned.fingerprint, seenFp)
        }
    }

    /**
     * Pin from a migration QR — we already trust the key because it came from our own device.
     * Computes the fingerprint from the pubKeyBase64 and stores it exactly like pin().
     */
    fun pinFromMigration(context: Context, relayUrl: String, pubKeyBase64: String) {
        val fp = computeFingerprint(pubKeyBase64)
        val url = relayUrl.trimEnd('/')
        prefs(context).edit()
            .putString(prefKey(url, "pub"),         pubKeyBase64)
            .putString(prefKey(url, "fingerprint"), fp)
            .putLong  (prefKey(url, "pinned_at"),   System.currentTimeMillis())
            .apply()
        Log.i(TAG, "Pinned key from migration for $url fp=$fp")
    }

    /**
     * Clear the pin for a relay URL (use when user intentionally re-registers).
     */
    fun clearPin(context: Context, relayUrl: String) {
        prefs(context).edit()
            .remove(prefKey(relayUrl, "pub"))
            .remove(prefKey(relayUrl, "fingerprint"))
            .remove(prefKey(relayUrl, "pinned_at"))
            .apply()
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun prefKey(relayUrl: String, field: String): String {
        // Safe storage key: hash the URL so special chars don't cause issues
        val hash = MessageDigest.getInstance("SHA-256")
            .digest(relayUrl.trimEnd('/').toByteArray())
            .joinToString("") { "%02x".format(it) }
            .take(16)
        return "pin_${hash}_$field"
    }

    private fun computeFingerprint(pubBase64: String): String {
        val bytes = Base64.decode(pubBase64, Base64.DEFAULT)
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
        return digest.joinToString(":") { "%02x".format(it) }
    }

    private fun prefs(context: Context) = EncryptedSharedPreferences.create(
        context, "fortispass_server_trust",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
}
