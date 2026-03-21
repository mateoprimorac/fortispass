package com.fortispass.ui

import android.content.Context
import androidx.appcompat.app.AppCompatActivity
import com.fortispass.ui.util.LocaleManager
import com.fortispass.ui.util.ThemeManager

/**
 * All Activities extend this.
 *
 * - attachBaseContext wraps with locale so getString() returns translated strings.
 * - onCreate calls setTheme() before super so ?attr/ colors resolve from the right style.
 */
abstract class BaseActivity : AppCompatActivity() {

    override fun attachBaseContext(newBase: Context) {
        val localeWrapped = LocaleManager.wrap(newBase)
        super.attachBaseContext(localeWrapped)
    }

    override fun onCreate(savedInstanceState: android.os.Bundle?) {
        // Set night mode before super.onCreate() so AppCompat picks it up before
        // any views inflate. This is the only place setDefaultNightMode() is called —
        // calling it during a live theme transition triggers AppCompat's recreate()
        // on the current activity, which is what caused the light↔dark flicker.
        val nightMode = when (ThemeManager.getSaved(this)) {
            "light"  -> androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO
            "system" -> androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
            else     -> androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES
        }
        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(nightMode)
        ThemeManager.applyTheme(this)   // must be before super.onCreate / setContentView
        super.onCreate(savedInstanceState)
    }
}
