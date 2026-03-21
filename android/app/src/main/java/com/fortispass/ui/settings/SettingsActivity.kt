package com.fortispass.ui.settings

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.Color
import android.os.Bundle
import android.os.CountDownTimer
import android.util.Base64
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.gridlayout.widget.GridLayout
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import androidx.lifecycle.lifecycleScope
import com.fortispass.R
import com.fortispass.databinding.ActivitySettingsBinding
import com.fortispass.ui.BaseActivity
import com.fortispass.ui.MainActivity
import com.fortispass.ui.setup.SetupActivity
import com.fortispass.ui.unlock.QRScanActivity
import com.fortispass.ui.util.LocaleManager
import com.fortispass.ui.util.ThemeManager
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom

class SettingsActivity : BaseActivity() {

    private lateinit var binding: ActivitySettingsBinding

    override fun onResume() {
        super.onResume()
        checkMnemonicStatus()
        loadDeviceList()
    }

    // ── Theme definitions ─────────────────────────────────────────────────────
    private data class ThemeDef(val id: String, val labelRes: Int)
    private val themes = listOf(
        ThemeDef("dark",   R.string.theme_dark),
        ThemeDef("light",  R.string.theme_light),
        ThemeDef("system", R.string.theme_system),
        ThemeDef("madoka", R.string.theme_madoka),
        ThemeDef("homura", R.string.theme_homura),
        ThemeDef("mami",   R.string.theme_mami),
        ThemeDef("sayaka", R.string.theme_sayaka),
        ThemeDef("kyoko",  R.string.theme_kyoko),
    )

    // ── Language definitions ──────────────────────────────────────────────────
    private data class LangDef(val code: String, val nativeName: String)
    private val languages = listOf(
        LangDef("en", "English"),   LangDef("es", "Español"),
        LangDef("de", "Deutsch"),   LangDef("hr", "Hrvatski"),
        LangDef("it", "Italiano"),  LangDef("zh", "普通话"),
        LangDef("ru", "Русский"),   LangDef("ja", "日本語"),
        LangDef("fr", "Français"),  LangDef("ar", "العربية"),
        LangDef("hi", "हिन्दी"),     LangDef("ko", "한국어"),
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnBack.setOnClickListener { finish() }

        buildThemeGrid()
        buildLangGrid()

        binding.btnAddDevice.backgroundTintList =
            android.content.res.ColorStateList.valueOf(0xFF888888.toInt())
        binding.btnAddDevice.setOnClickListener {
            startActivity(Intent(this, AddDeviceActivity::class.java))
        }

        binding.btnExportMigration.setOnClickListener {
            requireBiometric(
                title    = getString(R.string.biometric_title),
                subtitle = getString(R.string.migration_biometric_subtitle),
            ) { showMigrationExport() }
        }

        binding.btnRecoveryPhrase.setOnClickListener {
            requireBiometric(
                title    = getString(R.string.biometric_title),
                subtitle = getString(R.string.recovery_biometric_subtitle),
            ) { showRecoveryPhrase(null) }
        }

        // Show migration + danger zone only when this device is registered
        val hasRegistration = try {
            EncryptedSharedPreferences.create(
                this, "fortispass_device",
                MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            ).getString("device_id", null) != null
        } catch (_: Exception) { false }
        binding.layoutRegisteredSections.visibility =
            if (hasRegistration) android.view.View.VISIBLE else android.view.View.GONE

        binding.btnReRegister.setOnClickListener {
            // Block logout until the recovery phrase has been confirmed
            val (relayUrl, authToken) = readDevicePrefs() ?: return@setOnClickListener
            lifecycleScope.launch(Dispatchers.IO) {
                val mnemonicConfirmed = try {
                    val url = URL("$relayUrl/api/v1/recovery/mnemonic-status")
                    val conn = (url.openConnection() as HttpURLConnection).apply {
                        requestMethod = "GET"
                        setRequestProperty("Authorization", "Bearer $authToken")
                        connectTimeout = 5_000; readTimeout = 5_000
                    }
                    if (conn.responseCode == 200) {
                        JSONObject(conn.inputStream.bufferedReader().readText())
                            .optBoolean("confirmed", false)
                    } else false
                } catch (_: Exception) { false }

                withContext(Dispatchers.Main) {
                    if (!mnemonicConfirmed) {
                        AlertDialog.Builder(this@SettingsActivity)
                            .setTitle(getString(R.string.logout_blocked_title))
                            .setMessage(getString(R.string.logout_blocked_message))
                            .setPositiveButton(getString(R.string.ok), null)
                            .show()
                    } else {
                        requireBiometric(
                            title    = getString(R.string.biometric_title),
                            subtitle = getString(R.string.re_register_biometric_subtitle),
                        ) {
                            AlertDialog.Builder(this@SettingsActivity)
                                .setTitle(getString(R.string.re_register_title))
                                .setMessage(getString(R.string.re_register_message))
                                .setPositiveButton(getString(R.string.re_register_confirm)) { _, _ ->
                                    clearRegistration()
                                    startActivity(Intent(this@SettingsActivity, SetupActivity::class.java)
                                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
                                    finish()
                                }
                                .setNegativeButton(getString(R.string.cancel), null)
                                .show()
                        }
                    }
                }
            }
        }
    }

    // ── Theme-aware background helper ─────────────────────────────────────────
    private fun resolveThemeColor(attrId: Int): Int {
        val ta = obtainStyledAttributes(intArrayOf(attrId))
        val color = ta.getColor(0, 0xFF222233.toInt())
        ta.recycle()
        return color
    }

    private fun makeItemBg(selected: Boolean, accent: Int): android.graphics.drawable.GradientDrawable {
        val bg2    = resolveThemeColor(com.fortispass.R.attr.bioColorBg2)
        val border = resolveThemeColor(com.fortispass.R.attr.bioColorBorder)
        val dp = resources.displayMetrics.density
        return android.graphics.drawable.GradientDrawable().apply {
            shape = android.graphics.drawable.GradientDrawable.RECTANGLE
            cornerRadius = 10 * dp
            setColor(bg2)
            if (selected) setStroke((2 * dp).toInt(), accent)
            else          setStroke((1 * dp).toInt(), border)
        }
    }

    // ── Theme grid ────────────────────────────────────────────────────────────
    private fun buildThemeGrid() {
        val grid = binding.themeGrid
        grid.columnCount = 4
        val saved = ThemeManager.getSaved(this)
        val dp = resources.displayMetrics.density

        themes.forEach { theme ->
            val colors = ThemeManager.swatchFor(theme.id)
            val isSelected = theme.id == saved
            val container = android.widget.LinearLayout(this).apply {
                orientation = android.widget.LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                val pad = (6 * dp).toInt()
                setPadding(pad, pad, pad, pad)
                isClickable = true; isFocusable = true
                background = makeItemBg(isSelected, colors.accent)
                tag = theme.id
                setOnClickListener { selectTheme(theme.id, grid) }
            }

            val swatch = View(this).apply {
                layoutParams = android.widget.LinearLayout.LayoutParams(
                    (40 * dp).toInt(), (24 * dp).toInt()
                ).also { it.bottomMargin = (5 * dp).toInt() }
                background = android.graphics.drawable.GradientDrawable().apply {
                    setColor(colors.bg)
                    cornerRadius = 6 * dp
                    setStroke((2 * dp).toInt(), colors.accent)
                }
            }

            val name = TextView(this).apply {
                text = getString(theme.labelRes)
                textSize = 11f
                setTextColor(if (isSelected) colors.accent else resolveThemeColor(com.fortispass.R.attr.bioColorText2))
                gravity = Gravity.CENTER
            }

            container.addView(swatch)
            container.addView(name)

            val params = GridLayout.LayoutParams().apply {
                width = 0
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1, 1f)
                setMargins((5 * dp).toInt(), (5 * dp).toInt(), (5 * dp).toInt(), (5 * dp).toInt())
            }
            grid.addView(container, params)
        }
    }

    private fun selectTheme(themeId: String, grid: GridLayout) {
        ThemeManager.save(this, themeId)
        // setDefaultNightMode is NOT called here. Calling it on the current activity
        // triggers AppCompat's recreate() which causes the light↔dark flicker even
        // when the overlay is fully opaque. It is now called in BaseActivity.onCreate()
        // of the new activity stack that starts below, so it fires quietly before any
        // views inflate on the incoming screen.

        // Highlight selection immediately for visual feedback
        for (i in 0 until grid.childCount) {
            val child = grid.getChildAt(i) as? android.widget.LinearLayout ?: continue
            val id = child.tag as? String ?: continue
            val accent = ThemeManager.swatchFor(id).accent
            child.background = makeItemBg(id == themeId, accent)
        }

        // Fade overlay to black, then start fresh stack — new activities apply
        // the correct night mode themselves via BaseActivity.onCreate()
        val overlay = findViewById<android.view.View>(R.id.theme_fade_overlay)
        overlay?.let {
            it.visibility = android.view.View.VISIBLE
            it.animate()
                .alpha(1f)
                .setDuration(120)
                .withEndAction {
                    startActivity(
                        Intent(this, MainActivity::class.java)
                            .putExtra("open_settings", true)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    )
                    overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
                }
                .start()
        } ?: run {
            grid.postDelayed({
                startActivity(
                    Intent(this, MainActivity::class.java)
                        .putExtra("open_settings", true)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                )
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
            }, 160)
        }
    }


    // ── Language grid ─────────────────────────────────────────────────────────
    private fun buildLangGrid() {
        val grid = binding.langGrid
        grid.columnCount = 3
        val saved = LocaleManager.getSaved(this)
        val dp = resources.displayMetrics.density
        val accentColor = ThemeManager.accentColor(this)
        val text2Color  = resolveThemeColor(com.fortispass.R.attr.bioColorText2)

        languages.forEach { lang ->
            val isSelected = lang.code == saved
            val container = android.widget.LinearLayout(this).apply {
                orientation = android.widget.LinearLayout.VERTICAL
                gravity = Gravity.CENTER
                val pad = (10 * dp).toInt()
                setPadding(pad, pad, pad, pad)
                isClickable = true; isFocusable = true
                background = makeItemBg(isSelected, accentColor)
                tag = lang.code
                setOnClickListener { selectLanguage(lang.code, grid) }
            }
            val label = TextView(this).apply {
                text = lang.nativeName
                textSize = 12f
                setTextColor(if (isSelected) accentColor else text2Color)
                gravity = Gravity.CENTER
            }
            container.addView(label)
            val params = GridLayout.LayoutParams().apply {
                width = 0
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1, 1f)
                setMargins((5 * dp).toInt(), (5 * dp).toInt(), (5 * dp).toInt(), (5 * dp).toInt())
            }
            grid.addView(container, params)
        }
    }

    // ── Text size slider ──────────────────────────────────────────────────────
    private fun selectLanguage(code: String, grid: GridLayout) {
        // Highlight selection immediately so user sees feedback
        val accentColor = ThemeManager.accentColor(this)
        val text2Color  = resolveThemeColor(com.fortispass.R.attr.bioColorText2)
        for (i in 0 until grid.childCount) {
            val child = grid.getChildAt(i) as? android.widget.LinearLayout ?: continue
            val id = child.tag as? String ?: continue
            val selected = id == code
            child.background = makeItemBg(selected, accentColor)
            (child.getChildAt(0) as? TextView)?.setTextColor(if (selected) accentColor else text2Color)
        }
        // Apply locale and restart from MainActivity so all activities get fresh context
        grid.postDelayed({
            LocaleManager.applyAndRestart(this,
                code,
                Intent(this, MainActivity::class.java))
        }, 150)
    }

    // ── Biometric gate ────────────────────────────────────────────────────────
    /**
     * Show a biometric prompt (no CryptoObject — confirmation only).
     * [onSuccess] is called on the main thread only if authentication succeeds.
     * Silent on user-cancel; shows a toast on hardware error.
     */
    private fun requireBiometric(title: String, subtitle: String, onSuccess: () -> Unit) {
        val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    onSuccess()
                }
                override fun onAuthenticationError(code: Int, msg: CharSequence) {
                    // ERROR_NEGATIVE_BUTTON and ERROR_USER_CANCELED are silent (user chose to cancel)
                    if (code != BiometricPrompt.ERROR_NEGATIVE_BUTTON &&
                        code != BiometricPrompt.ERROR_USER_CANCELED) {
                        Toast.makeText(this@SettingsActivity, msg, Toast.LENGTH_SHORT).show()
                    }
                }
                override fun onAuthenticationFailed() {
                    Toast.makeText(this@SettingsActivity,
                        getString(R.string.biometric_not_recognised), Toast.LENGTH_SHORT).show()
                }
            })
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .setSubtitle(subtitle)
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText(getString(R.string.cancel))
            .build()
        prompt.authenticate(info)
    }

    // ── Migration export ──────────────────────────────────────────────────────
    private fun showMigrationExport() {
        val encPrefs = try {
            EncryptedSharedPreferences.create(
                this, "fortispass_device",
                MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) { showError("Could not read device data: ${e.message}"); return }

        val relayUrl   = encPrefs.getString("relay_url",       null) ?: run { showError(getString(R.string.not_registered)); return }
        val authToken  = encPrefs.getString("auth_token",      null) ?: run { showError(getString(R.string.not_registered)); return }
        val deviceId   = encPrefs.getString("device_id",       null) ?: run { showError(getString(R.string.not_registered)); return }
        val serverPub  = encPrefs.getString("server_pub_key",  null) ?: run { showError(getString(R.string.not_registered)); return }
        val signingKey = encPrefs.getString("signing_priv_key",null) ?: run { showError(getString(R.string.not_registered)); return }

        val nonce       = ByteArray(16).also { SecureRandom().nextBytes(it) }
        // migration_id: 32 random bytes used to coordinate the wipe confirmation via server
        val migrationId = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val migrationIdB64 = Base64.encodeToString(migrationId, Base64.NO_WRAP or Base64.URL_SAFE)
        val expiry = System.currentTimeMillis() / 1000 + 180
        val payload = JSONObject().apply {
            put("v", 2); put("relay_url", relayUrl); put("auth_token", authToken)
            put("device_id", deviceId); put("server_pub", serverPub); put("signing_key", signingKey)
            put("nonce", Base64.encodeToString(nonce, Base64.NO_WRAP))
            put("migration_id", migrationIdB64)
            put("exp", expiry)
        }.toString()

        val qrBitmap = generateQR(payload, 600) ?: run { showError("Failed to generate QR"); return }

        val dialogView = layoutInflater.inflate(R.layout.dialog_migration_export, null)
        dialogView.findViewById<ImageView>(R.id.iv_migration_qr).setImageBitmap(qrBitmap)
        val expiryText = dialogView.findViewById<TextView>(R.id.tv_expiry)

        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .setNegativeButton(getString(R.string.done), null)
            .setCancelable(true)
            .create()

        var timer: CountDownTimer? = null
        var pollJob: Job? = null

        dialog.setOnShowListener {
            dialog.window?.setFlags(
                WindowManager.LayoutParams.FLAG_SECURE,
                WindowManager.LayoutParams.FLAG_SECURE
            )
            timer = object : CountDownTimer(180_000L, 1000L) {
                override fun onTick(ms: Long) {
                    val s = ms / 1000
                    expiryText.text = getString(R.string.migration_expiry, "${s / 60}:${"%02d".format(s % 60)}")
                }
                override fun onFinish() {
                    expiryText.text = getString(R.string.migration_expired)
                    dialogView.findViewById<ImageView>(R.id.iv_migration_qr)
                        .setColorFilter(0x88000000.toInt(), android.graphics.PorterDuff.Mode.SRC_ATOP)
                    pollJob?.cancel()
                }
            }.start()

            // Poll the server every 3 seconds for confirmation from the new device
            pollJob = lifecycleScope.launch(Dispatchers.IO) {
                while (isActive) {
                    delay(3_000L)
                    val confirmed = checkMigrationConfirmed(relayUrl, authToken, migrationIdB64)
                    if (confirmed) {
                        withContext(Dispatchers.Main) {
                            timer?.cancel()
                            pollJob?.cancel()
                            dialog.dismiss()
                            // Wipe this device — new device has successfully imported
                            clearRegistration()
                            Toast.makeText(
                                this@SettingsActivity,
                                getString(R.string.migration_wiped),
                                Toast.LENGTH_LONG
                            ).show()
                            startActivity(
                                Intent(this@SettingsActivity, SetupActivity::class.java)
                                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                            )
                        }
                        break
                    }
                }
            }
        }

        dialog.setOnDismissListener {
            timer?.cancel()
            pollJob?.cancel()
            dialog.window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
        dialog.show()
    }

    /** Returns true if the server reports the migration was confirmed by the new device. */
    private fun checkMigrationConfirmed(relayUrl: String, authToken: String, migrationId: String): Boolean {
        return try {
            val url = URL("$relayUrl/api/v1/migration/status/$migrationId")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "GET"
                setRequestProperty("Authorization", "Bearer $authToken")
                connectTimeout = 5_000
                readTimeout = 5_000
            }
            val status = conn.responseCode
            if (status == 200) {
                val body = conn.inputStream.bufferedReader().readText()
                JSONObject(body).optString("status") == "confirmed"
            } else false
        } catch (_: Exception) { false }
    }

    // ── Recovery phrase ───────────────────────────────────────────────────────

    /** Fetches mnemonic confirmation status from server; shows/hides the button. */
    private fun checkMnemonicStatus() {
        val (relayUrl, authToken) = readDevicePrefs() ?: return
        // Only show section when device is registered and not yet confirmed
        lifecycleScope.launch(Dispatchers.IO) {
            val confirmed = try {
                val url = URL("$relayUrl/api/v1/recovery/mnemonic-status")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    setRequestProperty("Authorization", "Bearer $authToken")
                    connectTimeout = 5_000; readTimeout = 5_000
                }
                if (conn.responseCode == 200) {
                    val body = conn.inputStream.bufferedReader().readText()
                    JSONObject(body).optBoolean("confirmed", false)
                } else true // on error hide the button (fail safe)
            } catch (_: Exception) { true }

            withContext(Dispatchers.Main) {
                val section = binding.layoutRecoverySection
                // Show only if registered AND not yet confirmed
                val isRegistered = binding.layoutRegisteredSections.visibility == android.view.View.VISIBLE
                section.visibility = if (isRegistered && !confirmed)
                    android.view.View.VISIBLE else android.view.View.GONE
            }
        }
    }

    /** BiometricPrompt with CryptoObject — needed to unwrap the vault key. */
    private fun requireBiometricWithCipher(onSuccess: (javax.crypto.Cipher) -> Unit) {
        val cipher = try {
            com.fortispass.crypto.KeyManager.getDecryptCipher(
                com.fortispass.crypto.KeyManager.getStoredVaultKeyIV(this)
            )
        } catch (e: Exception) {
            showError("Cannot access vault key: ${e.message}"); return
        }
        val prompt = androidx.biometric.BiometricPrompt(this,
            androidx.core.content.ContextCompat.getMainExecutor(this),
            object : androidx.biometric.BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: androidx.biometric.BiometricPrompt.AuthenticationResult) {
                    result.cryptoObject?.cipher?.let { onSuccess(it) }
                        ?: showError("Biometric cipher unavailable")
                }
                override fun onAuthenticationError(code: Int, msg: CharSequence) {
                    if (code != androidx.biometric.BiometricPrompt.ERROR_NEGATIVE_BUTTON &&
                        code != androidx.biometric.BiometricPrompt.ERROR_USER_CANCELED)
                        Toast.makeText(this@SettingsActivity, msg, Toast.LENGTH_SHORT).show()
                }
                override fun onAuthenticationFailed() {
                    Toast.makeText(this@SettingsActivity,
                        getString(R.string.biometric_not_recognised), Toast.LENGTH_SHORT).show()
                }
            })
        val info = androidx.biometric.BiometricPrompt.PromptInfo.Builder()
            .setTitle(getString(R.string.biometric_title))
            .setSubtitle(getString(R.string.recovery_biometric_subtitle))
            .setAllowedAuthenticators(androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText(getString(R.string.cancel))
            .build()
        prompt.authenticate(info, androidx.biometric.BiometricPrompt.CryptoObject(cipher))
    }

    private fun showRecoveryPhrase(@Suppress("UNUSED_PARAMETER") cipher: javax.crypto.Cipher? = null) {
        // Load phraseSeed from EncryptedSharedPreferences — this is the real recovery phrase
        val phraseSeedB64 = try {
            val prefs = EncryptedSharedPreferences.create(
                this, "fortispass_device",
                MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            prefs.getString("phrase_seed", null)
        } catch (e: Exception) {
            showError("Could not load recovery phrase seed: ${e.message}"); return
        } ?: run { showError("Recovery phrase not available for this vault."); return }

        val phraseSeed = android.util.Base64.decode(phraseSeedB64, android.util.Base64.NO_WRAP)
        val phrase = try {
            com.fortispass.crypto.MnemonicEngine.phraseFromSeed(phraseSeed, this)
        } finally {
            phraseSeed.fill(0)
        }
        val dialogView = layoutInflater.inflate(R.layout.dialog_recovery_phrase, null)
        val col1 = dialogView.findViewById<android.widget.LinearLayout>(R.id.ll_col1)
        val col2 = dialogView.findViewById<android.widget.LinearLayout>(R.id.ll_col2)
        val col3 = dialogView.findViewById<android.widget.LinearLayout>(R.id.ll_col3)

        phrase.forEachIndexed { i, word ->
            val tv = android.widget.TextView(this).apply {
                text = "${i + 1}. $word"
                textSize = 13f
                setTextColor(resolveThemeColor(R.attr.bioColorText))
                setPadding(0, 4, 0, 4)
            }
            when {
                i < 8  -> col1.addView(tv)
                i < 16 -> col2.addView(tv)
                else   -> col3.addView(tv)
            }
        }

        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .setPositiveButton(getString(R.string.recovery_phrase_next)) { _, _ ->
                showRecoveryVerify(phrase)
            }
            .setNegativeButton(getString(R.string.cancel)) { _, _ -> }
            .setCancelable(false)
            .create()

        dialog.setOnShowListener {
            dialog.window?.setFlags(
                android.view.WindowManager.LayoutParams.FLAG_SECURE,
                android.view.WindowManager.LayoutParams.FLAG_SECURE
            )
        }
        dialog.setOnDismissListener {
            dialog.window?.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        }
        dialog.show()
    }

    private fun showRecoveryVerify(phrase: List<String>) {
        // Pick 3 distinct random positions
        val positions = (0 until phrase.size).shuffled().take(3).sorted()
        val dialogView = layoutInflater.inflate(R.layout.dialog_recovery_verify, null)

        val labels = listOf(
            dialogView.findViewById<android.widget.TextView>(R.id.tv_word_label_1),
            dialogView.findViewById<android.widget.TextView>(R.id.tv_word_label_2),
            dialogView.findViewById<android.widget.TextView>(R.id.tv_word_label_3),
        )
        val inputs = listOf(
            dialogView.findViewById<android.widget.EditText>(R.id.et_word_1),
            dialogView.findViewById<android.widget.EditText>(R.id.et_word_2),
            dialogView.findViewById<android.widget.EditText>(R.id.et_word_3),
        )
        val errorTv = dialogView.findViewById<android.widget.TextView>(R.id.tv_verify_error)

        positions.forEachIndexed { i, pos ->
            labels[i].text = "${getString(R.string.recovery_word_hint)} #${pos + 1}"
            inputs[i].hint = "${getString(R.string.recovery_word_hint)} ${pos + 1}"
        }

        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .setPositiveButton(getString(R.string.recovery_verify_confirm), null) // set below
            .setNegativeButton(getString(R.string.cancel), null)
            .setCancelable(false)
            .create()

        dialog.setOnShowListener {
            dialog.window?.setFlags(
                android.view.WindowManager.LayoutParams.FLAG_SECURE,
                android.view.WindowManager.LayoutParams.FLAG_SECURE
            )
            // Override positive button so we can validate without auto-dismiss
            dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                val answers = inputs.map { it.text.toString() }
                if (com.fortispass.crypto.MnemonicEngine.verifyWords(phrase, positions, answers)) {
                    dialog.dismiss()
                    postMnemonicConfirmed()
                } else {
                    errorTv.text = getString(R.string.recovery_verify_wrong)
                    errorTv.visibility = android.view.View.VISIBLE
                    inputs.forEach { it.setBackgroundTintList(
                        android.content.res.ColorStateList.valueOf(
                            android.graphics.Color.parseColor("#DC2626"))) }
                }
            }
        }
        dialog.setOnDismissListener {
            dialog.window?.clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE)
        }
        dialog.show()
    }

    private fun postMnemonicConfirmed() {
        val (relayUrl, authToken) = readDevicePrefs() ?: run {
            showError(getString(R.string.recovery_server_error)); return
        }
        lifecycleScope.launch(Dispatchers.IO) {
            val ok = try {
                val url = URL("$relayUrl/api/v1/recovery/confirm-mnemonic")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    setRequestProperty("Authorization", "Bearer $authToken")
                    setRequestProperty("Content-Type", "application/json")
                    doOutput = true
                    connectTimeout = 8_000; readTimeout = 8_000
                }
                conn.outputStream.use { it.write("{}".toByteArray()) }
                conn.responseCode == 200
            } catch (_: Exception) { false }

            withContext(Dispatchers.Main) {
                if (ok) {
                    binding.layoutRecoverySection.visibility = android.view.View.GONE
                    Toast.makeText(this@SettingsActivity,
                        getString(R.string.recovery_confirm_success), Toast.LENGTH_LONG).show()
                } else {
                    showError(getString(R.string.recovery_server_error))
                }
            }
        }
    }

    /** Returns Pair(relayUrl, authToken) from EncryptedSharedPreferences or null. */
    // ── Device list ────────────────────────────────────────────────────────────

    private fun loadDeviceList() {
        val (relayUrl, authToken) = readDevicePrefs() ?: return
        val currentDeviceId = try {
            EncryptedSharedPreferences.create(
                this, "fortispass_device",
                MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            ).getString("device_id", null)
        } catch (_: Exception) { null }

        lifecycleScope.launch(Dispatchers.IO) {
            // Fetch device list — 3s timeout for faster failure detection
            val devText = try {
                val conn = (java.net.URL("$relayUrl/api/v1/devices")
                    .openConnection() as java.net.HttpURLConnection).apply {
                    requestMethod = "GET"
                    setRequestProperty("Authorization", "Bearer $authToken")
                    connectTimeout = 3_000; readTimeout = 3_000
                }
                val code = conn.responseCode
                if (code == 200) conn.inputStream.bufferedReader().readText()
                else { android.util.Log.w("FP_Devices", "GET /devices returned $code"); null }
            } catch (e: Exception) { android.util.Log.w("FP_Devices", "fetch failed: $e"); null }

            // Fetch max devices from server info — 3s timeout
            val maxDev = try {
                val conn = (java.net.URL("$relayUrl/api/v1/server/info")
                    .openConnection() as java.net.HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = 3_000; readTimeout = 3_000
                }
                if (conn.responseCode == 200) {
                    org.json.JSONObject(conn.inputStream.bufferedReader().readText())
                        .optInt("max_devices_per_vault", 3)
                } else 3
            } catch (_: Exception) { 3 }

            withContext(Dispatchers.Main) {
                if (devText == null) {
                    showDevicesOffline()
                    return@withContext
                }
                try {
                    val arr = org.json.JSONArray(devText)
                    renderDeviceList(arr, maxDev, currentDeviceId)
                    // Enable Add Device — use theme accent color
                    binding.btnAddDevice.isEnabled = true
                    binding.btnAddDevice.backgroundTintList =
                        android.content.res.ColorStateList.valueOf(resolveThemeColor(R.attr.bioColorAccent))
                } catch (_: Exception) { showDevicesOffline() }
            }
        }
    }

    private fun renderDeviceList(arr: org.json.JSONArray, maxDevices: Int, currentDeviceId: String?) {
        val container  = binding.containerDevices
        val tvCount    = binding.tvDeviceCount
        val tvOffline  = binding.tvDevicesOffline
        container.removeAllViews()
        tvOffline.visibility = android.view.View.GONE

        val dp  = resources.displayMetrics.density
        val fmt = java.text.SimpleDateFormat("MMM d, yyyy", java.util.Locale.getDefault())

        var activeCount = 0
        for (i in 0 until arr.length()) {
            val dev = arr.getJSONObject(i)
            if (dev.optBoolean("is_revoked", false)) continue
            activeCount++

            // ── Row container ──────────────────────────────────────────────
            val row = android.widget.LinearLayout(this).apply {
                orientation = android.widget.LinearLayout.HORIZONTAL
                gravity = android.view.Gravity.CENTER_VERTICAL
                layoutParams = android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                    android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
                ).also { it.bottomMargin = (10 * dp).toInt() }
            }

            // ── Dot ────────────────────────────────────────────────────────
            val dot = android.widget.TextView(this).apply {
                text = "●"
                textSize = 14f
                setTextColor(resolveThemeColor(R.attr.bioColorAccent))
                setPadding(0, 0, (10 * dp).toInt(), 0)
            }

            // ── Name column ────────────────────────────────────────────────
            val nameCol = android.widget.LinearLayout(this).apply {
                orientation = android.widget.LinearLayout.VERTICAL
                layoutParams = android.widget.LinearLayout.LayoutParams(
                    0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            }

            val isSelf = dev.optString("id") == currentDeviceId

            // Name + optional badge on same horizontal row
            val nameRow = android.widget.LinearLayout(this).apply {
                orientation = android.widget.LinearLayout.HORIZONTAL
                gravity = android.view.Gravity.CENTER_VERTICAL
                layoutParams = android.widget.LinearLayout.LayoutParams(
                    android.widget.LinearLayout.LayoutParams.MATCH_PARENT,
                    android.widget.LinearLayout.LayoutParams.WRAP_CONTENT)
            }

            val tvName = android.widget.TextView(this).apply {
                text = dev.optString("name", "Unknown")
                textSize = 14f
                setTextColor(resolveThemeColor(R.attr.bioColorText))
                if (isSelf) setTypeface(null, android.graphics.Typeface.BOLD)
            }
            nameRow.addView(tvName)

            if (isSelf) {
                val badge = android.widget.TextView(this).apply {
                    text = getString(R.string.device_this)
                    textSize = 10f
                    setTextColor(android.graphics.Color.WHITE)
                    val bg = android.graphics.drawable.GradientDrawable().apply {
                        shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                        cornerRadius = (4 * resources.displayMetrics.density)
                        setColor(resolveThemeColor(R.attr.bioColorAccent))
                    }
                    background = bg
                    setPadding((5 * dp).toInt(), (2 * dp).toInt(),
                               (5 * dp).toInt(), (2 * dp).toInt())
                    layoutParams = android.widget.LinearLayout.LayoutParams(
                        android.widget.LinearLayout.LayoutParams.WRAP_CONTENT,
                        android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
                    ).also { it.marginStart = (8 * dp).toInt() }
                }
                nameRow.addView(badge)
            }

            val dateStr = dev.optString("created_at", "").take(10).let { raw ->
                try {
                    val sdf = java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.US)
                    getString(R.string.device_joined, fmt.format(sdf.parse(raw)!!))
                } catch (_: Exception) { raw }
            }
            val tvDate = android.widget.TextView(this).apply {
                text = dateStr
                textSize = 12f
                setTextColor(resolveThemeColor(R.attr.bioColorText2))
            }

            nameCol.addView(nameRow)
            nameCol.addView(tvDate)
            row.addView(dot)
            row.addView(nameCol)

            // Pencil icon — only for this device
            if (isSelf) {
                val devId = dev.optString("id")
                val pencil = android.widget.ImageButton(this).apply {
                    setImageDrawable(androidx.core.content.ContextCompat.getDrawable(
                        this@SettingsActivity, R.drawable.ic_pencil))
                    background = null
                    imageTintList = android.content.res.ColorStateList.valueOf(
                        resolveThemeColor(R.attr.bioColorText2))
                    layoutParams = android.widget.LinearLayout.LayoutParams(
                        android.widget.LinearLayout.LayoutParams.WRAP_CONTENT,
                        android.widget.LinearLayout.LayoutParams.WRAP_CONTENT
                    ).also { it.marginStart = (8 * dp).toInt() }
                    contentDescription = getString(R.string.rename_device)
                    setOnClickListener { showRenameDialog(devId, tvName.text.toString()) }
                }
                row.addView(pencil)
            }

            container.addView(row)
        }

        tvCount.text = getString(R.string.device_count_fmt, activeCount, maxDevices)
        tvCount.setTextColor(
            if (activeCount >= maxDevices) android.graphics.Color.parseColor("#DC2626")
            else resolveThemeColor(R.attr.bioColorText2)
        )
    }

    private fun showDevicesOffline() {
        binding.containerDevices.removeAllViews()
        binding.tvDevicesOffline.visibility = android.view.View.VISIBLE
        binding.tvDeviceCount.text = ""
        binding.btnAddDevice.isEnabled = false
        binding.btnAddDevice.backgroundTintList =
            android.content.res.ColorStateList.valueOf(0xFF888888.toInt())
    }

    private fun showRenameDialog(deviceId: String, currentName: String) {
        val input = android.widget.EditText(this).apply {
            setText(currentName)
            selectAll()
            inputType = android.text.InputType.TYPE_CLASS_TEXT
            val dp = resources.displayMetrics.density
            setPadding((16 * dp).toInt(), (12 * dp).toInt(), (16 * dp).toInt(), (12 * dp).toInt())
        }
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.rename_device))
            .setView(input)
            .setPositiveButton(getString(R.string.ok)) { _, _ ->
                val newName = input.text.toString().trim()
                if (newName.isEmpty()) return@setPositiveButton
                val (relayUrl, authToken) = readDevicePrefs() ?: return@setPositiveButton
                lifecycleScope.launch(Dispatchers.IO) {
                    try {
                        val body = org.json.JSONObject().apply { put("name", newName) }.toString()
                        val conn = (java.net.URL("$relayUrl/api/v1/devices/$deviceId/rename")
                            .openConnection() as java.net.HttpURLConnection).apply {
                            requestMethod = "PATCH"
                            setRequestProperty("Authorization", "Bearer $authToken")
                            setRequestProperty("Content-Type", "application/json")
                            doOutput = true
                            connectTimeout = 5_000; readTimeout = 5_000
                        }
                        conn.outputStream.use { it.write(body.toByteArray()) }
                        val ok = conn.responseCode == 200
                        withContext(Dispatchers.Main) {
                            if (ok) {
                                Toast.makeText(this@SettingsActivity,
                                    getString(R.string.rename_device_success), Toast.LENGTH_SHORT).show()
                                loadDeviceList()  // refresh
                            } else {
                                showError(getString(R.string.rename_device_error, "HTTP ${conn.responseCode}"))
                            }
                        }
                    } catch (e: Exception) {
                        withContext(Dispatchers.Main) {
                            showError(getString(R.string.rename_device_error, e.message ?: ""))
                        }
                    }
                }
            }
            .setNegativeButton(getString(R.string.cancel), null)
            .show()
    }

    private fun readDevicePrefs(): Pair<String, String>? {
        return try {
            val prefs = EncryptedSharedPreferences.create(
                this, "fortispass_device",
                MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            val relay = prefs.getString("relay_url", null) ?: return null
            val token = prefs.getString("auth_token", null) ?: return null
            Pair(relay, token)
        } catch (_: Exception) { null }
    }

    private fun generateQR(content: String, size: Int): Bitmap? = try {
        val bits = QRCodeWriter().encode(content, BarcodeFormat.QR_CODE, size, size)
        val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.RGB_565)
        for (x in 0 until size) for (y in 0 until size)
            bmp.setPixel(x, y, if (bits[x, y]) Color.BLACK else Color.WHITE)
        bmp
    } catch (_: Exception) { null }

    private fun showError(msg: String) {
        AlertDialog.Builder(this).setTitle(getString(R.string.error)).setMessage(msg)
            .setPositiveButton(getString(R.string.ok), null).show()
    }

    private fun clearRegistration() {
        listOf("fortispass_device", "fortispass_keys").forEach { name ->
            try {
                EncryptedSharedPreferences.create(
                    this, name,
                    MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                ).edit().clear().apply()
            } catch (_: Exception) {}
        }
        try {
            val ks = java.security.KeyStore.getInstance("AndroidKeyStore").also { it.load(null) }
            if (ks.containsAlias("fortispass_vault_key_wrapper")) ks.deleteEntry("fortispass_vault_key_wrapper")
        } catch (_: Exception) {}
    }
}
