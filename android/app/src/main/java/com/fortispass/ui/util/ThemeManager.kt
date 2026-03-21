package com.fortispass.ui.util

import android.content.Context
import android.graphics.Color
import com.fortispass.R

/**
 * Manages the app visual theme.
 *
 * Night mode (for System theme) is set globally in FortispassApplication.onCreate().
 * Per-activity, applyTheme() calls setTheme() before super.onCreate() so the
 * correct style resource is active when views are inflated.
 *
 * All layout colors reference ?attr/ attributes defined in themes.xml,
 * so changing the style resource is all that's needed.
 */
object ThemeManager {

    private const val PREFS = "fortispass_settings"
    private const val KEY   = "theme"
    const val DEFAULT       = "dark"

    /** Colors used in the SettingsActivity grid swatches (never for layout tinting). */
    data class SwatchColors(val bg: Int, val accent: Int)

    private val swatches = mapOf(
        "dark"   to SwatchColors(Color.parseColor("#0E0E10"), Color.parseColor("#3A6FD8")),
        "light"  to SwatchColors(Color.parseColor("#F5F5FF"), Color.parseColor("#4040C8")),
        "system" to SwatchColors(Color.parseColor("#0E0E10"), Color.parseColor("#3A6FD8")),
        "madoka" to SwatchColors(Color.parseColor("#1A0F14"), Color.parseColor("#E8427A")),
        "homura" to SwatchColors(Color.parseColor("#0A0A12"), Color.parseColor("#7A50C8")),
        "mami"   to SwatchColors(Color.parseColor("#17130A"), Color.parseColor("#E8B820")),
        "sayaka" to SwatchColors(Color.parseColor("#091418"), Color.parseColor("#2090C8")),
        "kyoko"  to SwatchColors(Color.parseColor("#180A0A"), Color.parseColor("#D83020")),
    )

    private val styleMap = mapOf(
        "dark"   to R.style.Theme_Biokey,
        "light"  to R.style.Theme_Biokey_Light,
        "system" to R.style.Theme_Biokey_System,
        "madoka" to R.style.Theme_Biokey_Madoka,
        "homura" to R.style.Theme_Biokey_Homura,
        "mami"   to R.style.Theme_Biokey_Mami,
        "sayaka" to R.style.Theme_Biokey_Sayaka,
        "kyoko"  to R.style.Theme_Biokey_Kyoko,
    )

    fun getSaved(context: Context): String =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY, DEFAULT) ?: DEFAULT

    fun save(context: Context, themeId: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit().putString(KEY, themeId).apply()
    }

    /**
     * Call BEFORE super.onCreate() in every Activity (done via BaseActivity).
     * Sets the style resource so ?attr/ colors resolve correctly for this theme.
     */
    fun applyTheme(activity: androidx.appcompat.app.AppCompatActivity) {
        activity.setTheme(styleMap[getSaved(activity)] ?: R.style.Theme_Biokey)
    }

    fun swatchFor(id: String): SwatchColors = swatches[id] ?: swatches[DEFAULT]!!

    /** Accent color of the currently active theme — for programmatic tinting. */
    fun accentColor(context: Context): Int = swatches[getSaved(context)]?.accent
        ?: Color.parseColor("#3A6FD8")

    val allIds = listOf("dark", "light", "system", "madoka", "homura", "mami", "sayaka", "kyoko")
}
