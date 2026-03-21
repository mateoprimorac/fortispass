package com.fortispass.recovery

import com.fortispass.crypto.CryptoEngine
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Recovery key management using a simple wordlist-free approach.
 * Encodes the 32-byte recovery key as a hex string split into 8 groups of 8 chars.
 * Easy to write down, unambiguous, no dependency on a BIP39 wordlist.
 *
 * Example: "a3f2c1d0 9e8b7a6f 5c4d3e2b 1f0e9d8c 7b6a5f4e 3d2c1b0a 9f8e7d6c 5b4a3f2e"
 */
object RecoveryManager {

    fun generateRecoveryMaterial(vaultKey: ByteArray): Triple<ByteArray, String, ByteArray> {
        val recoveryKey = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val phrase = encodePhrase(recoveryKey)
        val blob = CryptoEngine.encryptForSession(vaultKey.copyOf(), recoveryKey)
        return Triple(recoveryKey, phrase, blob)
    }

    fun recoverVaultKey(phrase: String, encryptedVaultKey: ByteArray): ByteArray {
        val recoveryKey = decodePhrase(phrase)
        return try {
            CryptoEngine.decryptFromSession(encryptedVaultKey, recoveryKey)
        } finally {
            recoveryKey.fill(0)
        }
    }

    /** Encode 32 bytes as 8 groups of 8 hex chars separated by spaces. */
    fun encodePhrase(bytes: ByteArray): String {
        require(bytes.size == 32)
        val hex = bytes.joinToString("") { "%02x".format(it) }
        return hex.chunked(8).joinToString(" ")
    }

    /** Decode back to 32 bytes. Tolerant of extra whitespace and uppercase. */
    fun decodePhrase(phrase: String): ByteArray {
        val clean = phrase.trim().lowercase().replace(Regex("\\s+"), "")
        require(clean.length == 64) { "Recovery phrase must be 64 hex characters (8 groups of 8)" }
        require(clean.all { it in '0'..'9' || it in 'a'..'f' }) { "Invalid characters in recovery phrase" }
        return ByteArray(32) { i ->
            clean.substring(i * 2, i * 2 + 2).toInt(16).toByte()
        }
    }
}
