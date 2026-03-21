package com.fortispass.ui.util

import android.content.Context
import android.content.res.Configuration
import android.os.Build
import android.os.LocaleList
import androidx.appcompat.app.AppCompatDelegate
import java.util.Locale

/**
 * Manages the app language.
 *
 * Selection path:
 *   1. User picks a language → save(code) → setApplicationLocales(tag) → recreate()
 *   2. On next process start FortispassApplication reads the saved code and calls
 *      setApplicationLocales() again so it persists.
 *   3. attachBaseContext wraps the base context for any API level.
 */
object LocaleManager {

    private const val PREFS = "fortispass_settings"
    private const val KEY   = "language"
    const val DEFAULT       = "en"

    private val bcp47Map = mapOf(
        "en" to "en",    "es" to "es",   "de" to "de",
        "hr" to "hr",    "it" to "it",   "zh" to "zh-Hans",
        "ru" to "ru",    "ja" to "ja",   "fr" to "fr",
        "ar" to "ar",    "hi" to "hi",   "ko" to "ko",
    )

    fun toBcp47(code: String): String = bcp47Map[code] ?: code

    fun getSaved(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, DEFAULT) ?: DEFAULT

    fun save(context: Context, code: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, code).apply()
    }

    /**
     * Wrap a Context with the saved locale configuration.
     * Call from Activity.attachBaseContext() as a fallback for older APIs.
     * On API 33+ AppCompatDelegate handles this automatically, but wrapping
     * is harmless and ensures correctness on all API levels.
     */
    fun wrap(base: Context): Context {
        val code   = getSaved(base)
        val locale = Locale.forLanguageTag(toBcp47(code))
        Locale.setDefault(locale)

        val config = Configuration(base.resources.configuration)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            config.setLocales(LocaleList(locale))
        } else {
            @Suppress("DEPRECATION")
            config.locale = locale
        }
        config.setLayoutDirection(locale)
        return base.createConfigurationContext(config)
    }

    /**
     * Called when the user selects a new language.
     * Saves the choice and restarts the full activity stack so every Activity
     * picks up the new locale via attachBaseContext → LocaleManager.wrap().
     *
     * NOTE: AppCompatDelegate.setApplicationLocales() is intentionally NOT
     * called here. On API 33+ it schedules an in-place recreation of the
     * current Activity, which races with the CLEAR_TASK restart and can leave
     * AppCompat's locale state inconsistent. FortispassApplication.onCreate()
     * calls setApplicationLocales() once at process start; for within-process
     * language changes, LocaleManager.wrap() in attachBaseContext is sufficient.
     */
    fun applyAndRestart(context: Context, code: String, restartIntent: android.content.Intent) {
        save(context, code)
        restartIntent.addFlags(
            android.content.Intent.FLAG_ACTIVITY_NEW_TASK or
            android.content.Intent.FLAG_ACTIVITY_CLEAR_TASK
        )
        context.startActivity(restartIntent)
    }
}
