package com.fortispass

import android.app.Application
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import com.fortispass.ui.util.LocaleManager
import com.fortispass.ui.util.ThemeManager

/**
 * Application entry point.
 *
 * Sets the global night mode (for theme) and the per-app locale (for language)
 * once at process start so every Activity gets the right configuration from
 * the very first layout inflation.
 */
class FortispassApplication : Application() {

    override fun onCreate() {
        super.onCreate()

        // ── Theme: set night mode globally before any Activity starts ─────────
        val themeId = ThemeManager.getSaved(this)
        val nightMode = when (themeId) {
            "light"  -> AppCompatDelegate.MODE_NIGHT_NO
            "system" -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
            else     -> AppCompatDelegate.MODE_NIGHT_YES  // dark + all palette themes
        }
        AppCompatDelegate.setDefaultNightMode(nightMode)

        // ── Language: install per-app locale so every Context gets it ─────────
        val langCode = LocaleManager.getSaved(this)
        val bcp47 = LocaleManager.toBcp47(langCode)
        AppCompatDelegate.setApplicationLocales(
            LocaleListCompat.forLanguageTags(bcp47)
        )
    }
}
