package com.fortispass.ui.setup

import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.util.Base64
import android.util.TypedValue
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import com.fortispass.R
import com.fortispass.crypto.CryptoEngine
import com.fortispass.crypto.KeyManager
import com.fortispass.crypto.MnemonicEngine
import com.fortispass.network.ServerTrust
import com.fortispass.ui.MainActivity
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import javax.crypto.AEADBadTagException

/**
 * Recovery phrase login — 6 words per page, 4 pages total.
 * Relay URL always visible at the top; validated before leaving page 0.
 */
class RecoveryLoginActivity : com.fortispass.ui.BaseActivity() {

    private lateinit var etRelayUrl:      EditText
    private lateinit var tvPageIndicator: TextView
    private lateinit var containerWords:  LinearLayout
    private lateinit var tvStatus:        TextView
    private lateinit var btnPrev:         MaterialButton
    private lateinit var btnNext:         MaterialButton

    private val wordInputs = arrayOfNulls<EditText>(24)
    private var currentPage = 0
    private val WORDS_PER_PAGE = 6
    private val TOTAL_PAGES    = 4

    private var wordList: List<String> = emptyList()
    private var wordSet:  Set<String>  = emptySet()

    private val colorBorderDefault get() = resolveAttrColor(R.attr.bioColorBorder)
    private val colorBorderError   = Color.parseColor("#DC2626")
    private val colorBorderOk      = Color.parseColor("#16A34A")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_recovery_login)

        etRelayUrl      = findViewById(R.id.et_relay_url)
        tvPageIndicator = findViewById(R.id.tv_page_indicator)
        containerWords  = findViewById(R.id.container_words)
        tvStatus        = findViewById(R.id.tv_status)
        btnPrev         = findViewById(R.id.btn_prev)
        btnNext         = findViewById(R.id.btn_next)

        lifecycleScope.launch(Dispatchers.IO) {
            wordList = MnemonicEngine.loadWordList(this@RecoveryLoginActivity)
            wordSet  = wordList.toHashSet()
        }

        buildWordInputs()
        showPage(0)

        findViewById<MaterialButton>(R.id.btn_back).setOnClickListener { finish() }
        btnPrev.setOnClickListener { showPage(currentPage - 1) }
        btnNext.setOnClickListener { onNext() }
    }

    // ── Page management ────────────────────────────────────────────────────────

    private fun showPage(page: Int) {
        currentPage = page.coerceIn(0, TOTAL_PAGES - 1)

        val first = currentPage * WORDS_PER_PAGE + 1
        val last  = first + WORDS_PER_PAGE - 1
        tvPageIndicator.text = getString(R.string.words_page_indicator, first, last)

        containerWords.removeAllViews()
        val dp = resources.displayMetrics.density

        for (i in 0 until WORDS_PER_PAGE) {
            val wordIdx = currentPage * WORDS_PER_PAGE + i
            val et = wordInputs[wordIdx] ?: continue

            val row = LinearLayout(this).apply {
                orientation = LinearLayout.VERTICAL
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).also { it.bottomMargin = (10 * dp).toInt() }
            }

            val label = TextView(this).apply {
                text = getString(R.string.word_label, wordIdx + 1)
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 11f)
                setTextColor(resolveAttrColor(R.attr.bioColorAccent))
                setPadding(0, 0, 0, (3 * dp).toInt())
            }

            row.addView(label)
            (et.parent as? android.view.ViewGroup)?.removeView(et)
            row.addView(et)
            containerWords.addView(row)
        }

        // Focus first empty input on this page
        for (i in 0 until WORDS_PER_PAGE) {
            val et = wordInputs[currentPage * WORDS_PER_PAGE + i] ?: continue
            if (et.text.isEmpty()) { et.requestFocus(); break }
        }

        btnPrev.visibility = if (currentPage > 0) View.VISIBLE else View.GONE
        val isLastPage = currentPage == TOTAL_PAGES - 1
        btnNext.text = getString(if (isLastPage) R.string.restore else R.string.next)
        btnNext.setIconResource(if (isLastPage) R.drawable.ic_key else R.drawable.ic_arrow_forward)
        tvStatus.visibility = View.GONE
    }

    private fun onNext() {
        // Fix 2: Always validate relay URL first regardless of page
        val relayUrl = etRelayUrl.text.toString().trim().trimEnd('/')
        if (relayUrl.isEmpty()) {
            etRelayUrl.backgroundTintList = ColorStateList.valueOf(colorBorderError)
            etRelayUrl.requestFocus()
            showStatus(getString(R.string.recovery_login_relay_label) + " is required.", isError = true)
            return
        } else {
            etRelayUrl.backgroundTintList = ColorStateList.valueOf(colorBorderDefault)
        }

        // Validate current page words
        var pageOk = true
        for (i in 0 until WORDS_PER_PAGE) {
            val wordIdx = currentPage * WORDS_PER_PAGE + i
            val et = wordInputs[wordIdx] ?: continue
            val word = et.text.toString().trim().lowercase()
            if (word.isEmpty() || (wordSet.isNotEmpty() && word !in wordSet)) {
                tintInput(et, isError = true)
                if (pageOk) et.requestFocus()
                pageOk = false
            }
        }
        if (!pageOk) {
            showStatus(getString(R.string.recovery_word_unknown), isError = true)
            return
        }

        if (currentPage < TOTAL_PAGES - 1) {
            showPage(currentPage + 1)
        } else {
            startRestore(relayUrl)
        }
    }

    // ── Build 24 inputs ─────────────────────────────────────────────────────────

    private fun buildWordInputs() {
        val dp = resources.displayMetrics.density
        for (i in 0 until 24) {
            wordInputs[i] = EditText(this).apply {
                inputType = android.text.InputType.TYPE_CLASS_TEXT or
                            android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or
                            android.text.InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
                setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
                setTextColor(resolveAttrColor(R.attr.bioColorText))
                setHintTextColor(resolveAttrColor(R.attr.bioColorText3))
                backgroundTintList = ColorStateList.valueOf(colorBorderDefault)
                setPadding((12 * dp).toInt(), (12 * dp).toInt(), (12 * dp).toInt(), (12 * dp).toInt())
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                )
                val idx = i
                addTextChangedListener(object : TextWatcher {
                    override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                    override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                    override fun afterTextChanged(s: Editable?) {
                        val w = s.toString().trim().lowercase()
                        when {
                            w.isEmpty()                          -> tintInput(wordInputs[idx]!!, isNeutral = true)
                            wordSet.isNotEmpty() && w in wordSet -> tintInput(wordInputs[idx]!!, isOk = true)
                            wordSet.isNotEmpty()                 -> tintInput(wordInputs[idx]!!, isError = true)
                        }
                    }
                })
            }
        }
    }

    private fun tintInput(et: EditText, isError: Boolean = false,
                           isOk: Boolean = false, isNeutral: Boolean = false) {
        et.backgroundTintList = ColorStateList.valueOf(when {
            isError  -> colorBorderError
            isOk     -> colorBorderOk
            else     -> colorBorderDefault
        })
    }

    // ── Restore ─────────────────────────────────────────────────────────────────

    private fun startRestore(relayUrl: String) {
        val words = wordInputs.map { it?.text.toString().trim().lowercase() }
        btnNext.isEnabled = false; btnPrev.isEnabled = false
        showStatus(getString(R.string.recovery_login_fetching))

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // Derive vault key from phrase
                val vaultKey = MnemonicEngine.phraseToVaultKey(words, this@RecoveryLoginActivity)
                    ?: run {
                        withContext(Dispatchers.Main) {
                            showStatus(getString(R.string.recovery_login_wrong_phrase), isError = true)
                            resetButtons()
                        }
                        return@launch
                    }

                // Look up vault on server by HMAC hash
                val lookupHash = MnemonicEngine.vaultLookupHash(vaultKey)
                val vaultData  = fetchVault(relayUrl, lookupHash, vaultKey) ?: return@launch

                withContext(Dispatchers.Main) { showStatus(getString(R.string.recovery_login_decrypting)) }

                // Decrypt — AES-GCM tag mismatch = wrong phrase
                val encBytes  = Base64.decode(vaultData.getString("encrypted_blob"), Base64.DEFAULT)
                val decrypted = try {
                    CryptoEngine.decryptVault(encBytes, vaultKey)
                } catch (_: AEADBadTagException) {
                    vaultKey.fill(0)
                    withContext(Dispatchers.Main) {
                        showStatus(getString(R.string.recovery_login_wrong_phrase), isError = true)
                        resetButtons()
                    }
                    return@launch
                }

                withContext(Dispatchers.Main) { showStatus(getString(R.string.recovery_login_registering)) }

                val deviceName    = android.os.Build.MODEL
                val deviceKeys    = KeyManager.generateDeviceKeys()
                val freshVault          = CryptoEngine.encryptVault(decrypted, vaultKey)
                val wasConfirmed        = vaultData.optBoolean("mnemonic_confirmed", false)

                val regResult = registerDevice(relayUrl, deviceName, deviceKeys, freshVault, wasConfirmed)
                if (regResult == null) {
                    vaultKey.fill(0)
                    withContext(Dispatchers.Main) {
                        showStatus(getString(R.string.recovery_login_error, "Registration failed"), isError = true)
                        resetButtons()
                    }
                    return@launch
                }

                KeyManager.generateHardwareKey()
                KeyManager.wrapVaultKey(vaultKey, KeyManager.getEncryptCipher(), this@RecoveryLoginActivity)

                val phraseSeed = buildPhraseSeed(words)
                val encPrefs = androidx.security.crypto.EncryptedSharedPreferences.create(
                    this@RecoveryLoginActivity, "fortispass_device",
                    androidx.security.crypto.MasterKey.Builder(this@RecoveryLoginActivity)
                        .setKeyScheme(androidx.security.crypto.MasterKey.KeyScheme.AES256_GCM).build(),
                    androidx.security.crypto.EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    androidx.security.crypto.EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                )
                encPrefs.edit()
                    .putString("relay_url",        relayUrl)
                    .putString("auth_token",       regResult.getString("access_token"))
                    .putString("device_id",        regResult.getString("device_id"))
                    .putString("server_pub_key",   regResult.getString("server_pub_key"))
                    .putString("signing_priv_key", Base64.encodeToString(deviceKeys.signingPrivateKey, Base64.NO_WRAP))
                    .putString("phrase_seed",      Base64.encodeToString(phraseSeed, Base64.NO_WRAP))
                    .apply()
                phraseSeed.fill(0)

                ServerTrust.pinFromMigration(this@RecoveryLoginActivity, relayUrl,
                    regResult.getString("server_pub_key"))

                withContext(Dispatchers.Main) {
                    Toast.makeText(this@RecoveryLoginActivity,
                        getString(R.string.recovery_login_success), Toast.LENGTH_LONG).show()
                    startActivity(Intent(this@RecoveryLoginActivity, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
                    finish()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    showStatus(getString(R.string.recovery_login_error, e.message ?: "Unknown error"), isError = true)
                    resetButtons()
                }
            }
        }
    }

    // ── Network ─────────────────────────────────────────────────────────────────

    private suspend fun fetchVault(relayUrl: String, lookupHash: String, vaultKey: ByteArray): JSONObject? {
        return try {
            val body = JSONObject().apply { put("vault_lookup_hash", lookupHash) }.toString().toByteArray()
            val conn = (URL("$relayUrl/api/v1/recovery/vault").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"; setRequestProperty("Content-Type", "application/json")
                doOutput = true; connectTimeout = 10_000; readTimeout = 10_000
            }
            conn.outputStream.use { it.write(body) }
            when (val code = conn.responseCode) {
                200  -> JSONObject(conn.inputStream.bufferedReader().readText())
                404  -> {
                    vaultKey.fill(0)
                    withContext(Dispatchers.Main) {
                        showStatus(getString(R.string.recovery_login_device_not_found), isError = true)
                        resetButtons()
                    }
                    null
                }
                else -> {
                    vaultKey.fill(0)
                    withContext(Dispatchers.Main) {
                        showStatus(getString(R.string.recovery_login_error, "Server error $code"), isError = true)
                        resetButtons()
                    }
                    null
                }
            }
        } catch (e: Exception) {
            vaultKey.fill(0)
            withContext(Dispatchers.Main) {
                showStatus(getString(R.string.recovery_login_error, "Cannot reach server: ${e.message}"), isError = true)
                resetButtons()
            }
            null
        }
    }

    private fun registerDevice(relayUrl: String, name: String,
                               keys: KeyManager.DeviceKeys, vault: ByteArray,
                               mnemonicConfirmed: Boolean): JSONObject? {
        return try {
            val b64 = { b: ByteArray -> Base64.encodeToString(b, Base64.URL_SAFE or Base64.NO_WRAP) }
            val body = JSONObject().apply {
                put("device_name", name)
                put("device", JSONObject().apply {
                    put("name", name); put("type", "android")
                    put("dh_public_key",   b64(keys.dhPublicKey))
                    put("signing_pub_key", b64(keys.signingPublicKey))
                })
                put("initial_vault",      b64(vault))
                put("mnemonic_confirmed", mnemonicConfirmed)
            }.toString().toByteArray()
            val conn = (URL("$relayUrl/api/v1/auth/register").openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"; setRequestProperty("Content-Type", "application/json")
                doOutput = true; connectTimeout = 10_000; readTimeout = 10_000
            }
            conn.outputStream.use { it.write(body) }
            if (conn.responseCode == 201) JSONObject(conn.inputStream.bufferedReader().readText()) else null
        } catch (_: Exception) { null }
    }

    // ── Helpers ─────────────────────────────────────────────────────────────────

    private fun buildPhraseSeed(words: List<String>): ByteArray {
        val wi  = wordList.withIndex().associate { (i, w) -> w to i }
        val buf = ByteArray(MnemonicEngine.SEED_BYTES)
        words.forEachIndexed { i, w ->
            val idx = wi[w] ?: 0
            buf[i * 2]     = ((idx shr 8) and 0xFF).toByte()
            buf[i * 2 + 1] = (idx and 0xFF).toByte()
        }
        return buf
    }

    private fun showStatus(msg: String, isError: Boolean = false) {
        tvStatus.text = msg
        tvStatus.visibility = View.VISIBLE
        tvStatus.setTextColor(if (isError) colorBorderError else resolveAttrColor(R.attr.bioColorText2))
    }

    private fun resetButtons() { btnNext.isEnabled = true; btnPrev.isEnabled = true }

    private fun resolveAttrColor(attrId: Int): Int {
        val ta = obtainStyledAttributes(intArrayOf(attrId))
        val c  = ta.getColor(0, Color.GRAY); ta.recycle(); return c
    }
}
