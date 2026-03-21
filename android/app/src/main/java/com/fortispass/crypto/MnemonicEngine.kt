package com.fortispass.crypto

import android.content.Context
import java.security.SecureRandom

/**
 * Mnemonic phrase engine — Option A architecture.
 *
 * The recovery phrase IS the vault secret. The vault key is derived FROM the phrase.
 *
 * Derivation (phrase → vault key):
 *   1. Generate 24 random 16-bit indices, each in range [0, wordCount)
 *   2. phrase[n] = wordList[index[n]]
 *   3. packed = concat(BigEndian16(index[0]), ..., BigEndian16(index[23])) — 48 bytes
 *   4. vaultKey = HKDF-SHA256(ikm=packed, salt="fortispass-recovery-v1", info="", len=32)
 *
 * Entropy: 24 × log₂(~1919) ≈ 262 bits > 256-bit AES key — cryptographically strong.
 *
 * The phrase shown in Settings (deriveDisplayPhrase) uses a separate HKDF path
 * from the vault key and is a visual fingerprint only — NOT the recovery phrase.
 * The recovery phrase is the one generated at registration (generatePhraseAndKey).
 *
 * To allow Settings to show the real recovery phrase, the phrase_seed (packed indices,
 * 48 bytes) is stored in EncryptedSharedPreferences at registration time.
 */
object MnemonicEngine {

    const val RECOVERY_SALT = "fortispass-recovery-v1"
    const val WORD_COUNT    = 24
    const val SEED_BYTES    = WORD_COUNT * 2  // 48 bytes = 24 × 2

    @Volatile private var _wordList: List<String>? = null

    fun loadWordList(context: Context): List<String> {
        _wordList?.let { return it }
        synchronized(this) {
            _wordList?.let { return it }
            val words = context.assets.open("bip39_english.txt")
                .bufferedReader().readLines().filter { it.isNotBlank() }
            _wordList = words
            return words
        }
    }

    /**
     * Generates a new recovery phrase and derives the vault key from it.
     * Returns Triple(phrase, vaultKey, phraseSeed).
     * phraseSeed must be stored in EncryptedSharedPreferences so Settings can
     * re-display the real recovery phrase later.
     * CALLER must zero vaultKey and phraseSeed after use.
     */
    fun generatePhraseAndKey(context: Context): Triple<List<String>, ByteArray, ByteArray> {
        val wordList = loadWordList(context)
        val wc       = wordList.size
        val rawSeed  = ByteArray(SEED_BYTES)
        SecureRandom().nextBytes(rawSeed)

        // Normalise: map each 16-bit pair to a valid index and store back
        val packed = ByteArray(SEED_BYTES)
        val phrase = (0 until WORD_COUNT).map { i ->
            val hi  = rawSeed[i * 2].toInt() and 0xFF
            val lo  = rawSeed[i * 2 + 1].toInt() and 0xFF
            val idx = ((hi shl 8) or lo) % wc
            packed[i * 2]     = ((idx shr 8) and 0xFF).toByte()
            packed[i * 2 + 1] = (idx and 0xFF).toByte()
            wordList[idx]
        }
        rawSeed.fill(0)

        val salt     = RECOVERY_SALT.toByteArray(Charsets.UTF_8)
        val vaultKey = KeyManager.hkdfSHA256(packed, salt, ByteArray(0), 32)
        // packed is returned as phraseSeed — caller stores it, we don't fill it here
        return Triple(phrase, vaultKey, packed)
    }

    /**
     * Re-derives vault key from 24 words entered by the user.
     * Returns vault key or null if any word is not in the wordlist.
     * CALLER must zero the returned ByteArray.
     */
    fun phraseToVaultKey(words: List<String>, context: Context): ByteArray? {
        if (words.size != WORD_COUNT) return null
        val wordList  = loadWordList(context)
        val wordIndex = wordList.withIndex().associate { (i, w) -> w to i }

        val packed = ByteArray(SEED_BYTES)
        for ((i, word) in words.withIndex()) {
            val idx = wordIndex[word.lowercase().trim()] ?: run { packed.fill(0); return null }
            packed[i * 2]     = ((idx shr 8) and 0xFF).toByte()
            packed[i * 2 + 1] = (idx and 0xFF).toByte()
        }

        val salt = RECOVERY_SALT.toByteArray(Charsets.UTF_8)
        return try {
            KeyManager.hkdfSHA256(packed, salt, ByteArray(0), 32)
        } finally {
            packed.fill(0)
        }
    }

    /**
     * Re-derives the phrase from the stored phraseSeed (packed indices).
     * Used by Settings → View Recovery Phrase to show the real recovery phrase.
     * CALLER must zero phraseSeed after use.
     */
    fun phraseFromSeed(phraseSeed: ByteArray, context: Context): List<String> {
        require(phraseSeed.size == SEED_BYTES)
        val wordList = loadWordList(context)
        val wc       = wordList.size
        return (0 until WORD_COUNT).map { i ->
            val hi  = phraseSeed[i * 2].toInt() and 0xFF
            val lo  = phraseSeed[i * 2 + 1].toInt() and 0xFF
            wordList[((hi shl 8) or lo) % wc]
        }
    }

    fun verifyWords(phrase: List<String>, positions: List<Int>, answers: List<String>): Boolean {
        if (positions.size != answers.size) return false
        return positions.indices.all { i ->
            phrase[positions[i]].equals(answers[i].trim(), ignoreCase = true)
        }
    }

    /**
     * Computes vault_lookup_hash = HMAC-SHA256(vaultKey, "fortispass-vault-lookup-v1").
     * Sent to the server at registration and used during recovery to find the vault.
     * One-way: cannot derive vault key from the hash.
     * CALLER must zero vaultKey after calling.
     */
    fun vaultLookupHash(vaultKey: ByteArray): String {
        val mac = javax.crypto.Mac.getInstance("HmacSHA256")
        mac.init(javax.crypto.spec.SecretKeySpec(vaultKey, "HmacSHA256"))
        val hash = mac.doFinal("fortispass-vault-lookup-v1".toByteArray(Charsets.UTF_8))
        return android.util.Base64.encodeToString(hash, android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP)
    }
}
