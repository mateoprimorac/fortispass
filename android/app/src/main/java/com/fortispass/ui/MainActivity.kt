package com.fortispass.ui

import android.content.Intent
import android.content.res.ColorStateList
import android.os.Bundle
import androidx.lifecycle.lifecycleScope
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.fortispass.R
import com.fortispass.databinding.ActivityMainBinding
import com.fortispass.ui.setup.SetupActivity
import com.fortispass.ui.settings.SettingsActivity
import com.fortispass.ui.unlock.QRScanActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : com.fortispass.ui.BaseActivity() {

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        if (com.fortispass.ui.util.ThemeManager.getSaved(this) == "light") {
            binding.tvPass.setTextColor(android.graphics.Color.BLACK)
        }

        if (!isDeviceRegistered()) {
            startActivity(Intent(this, SetupActivity::class.java))
            finish()
            return
        }

        val ta = obtainStyledAttributes(intArrayOf(R.attr.bioColorText2))
        val strokeColor = ColorStateList.valueOf(ta.getColor(0, 0xFF8888A0.toInt()))
        ta.recycle()
        binding.btnSettings.strokeColor = strokeColor

        binding.btnScanQr.setOnClickListener {
            startActivity(Intent(this, QRScanActivity::class.java))
        }
        binding.btnSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
        if (intent.getBooleanExtra("open_settings", false)) {
            startActivity(Intent(this, SettingsActivity::class.java))
        }
    }

    override fun onResume() {
        super.onResume()
        checkRevocationStatus()
    }

    /**
     * On every resume, verify the auth token is still valid.
     * A 401 means this device was revoked (kicked) by another device.
     * Silently clear local data and redirect to setup screen.
     */
    private fun checkRevocationStatus() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val prefs = EncryptedSharedPreferences.create(
                    this@MainActivity, "fortispass_device",
                    MasterKey.Builder(this@MainActivity)
                        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                )
                val relayUrl  = prefs.getString("relay_url",  null) ?: return@launch
                val authToken = prefs.getString("auth_token", null) ?: return@launch

                val conn = (URL("$relayUrl/api/v1/devices").openConnection()
                        as HttpURLConnection).apply {
                    requestMethod = "GET"
                    setRequestProperty("Authorization", "Bearer $authToken")
                    connectTimeout = 5_000
                    readTimeout    = 5_000
                }
                val code = conn.responseCode

                if (code == 401) {
                    withContext(Dispatchers.Main) { clearAndGoToSetup() }
                }
            } catch (_: Exception) {
                // Network unreachable — don't log out, just skip the check
            }
        }
    }

    private fun clearAndGoToSetup() {
        listOf("fortispass_device", "fortispass_keys",
               "fortispass_settings", "fortispass_server_trust").forEach { name ->
            try {
                EncryptedSharedPreferences.create(
                    this, name,
                    MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                ).edit().clear().apply()
            } catch (_: Exception) {}
        }
        startActivity(Intent(this, SetupActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        finish()
    }

    private fun isDeviceRegistered(): Boolean = try {
        EncryptedSharedPreferences.create(
            this, "fortispass_device",
            MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        ).getString("device_id", null) != null
    } catch (e: Exception) { false }
}
