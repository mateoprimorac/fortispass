package com.fortispass.ui.setup

import android.content.Intent
import android.os.Bundle
import com.fortispass.R

class LoginVaultMenuActivity : com.fortispass.ui.BaseActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login_vault_menu)

        findViewById<com.google.android.material.button.MaterialButton>(R.id.btn_back)
            .setOnClickListener { finish() }

        findViewById<com.google.android.material.button.MaterialButton>(R.id.btn_import_old_phone)
            .setOnClickListener {
                startActivity(
                    Intent(this, com.fortispass.ui.unlock.QRScanActivity::class.java)
                        .putExtra("mode", "migration_import")
                )
            }

        // Scan an fp_invite QR from an existing device's Settings → Add Device screen
        findViewById<com.google.android.material.button.MaterialButton>(R.id.btn_scan_invite_qr)
            .setOnClickListener {
                startActivity(Intent(this, com.fortispass.ui.unlock.QRScanActivity::class.java))
            }

        findViewById<com.google.android.material.button.MaterialButton>(R.id.btn_use_recovery_phrase)
            .setOnClickListener {
                startActivity(Intent(this, RecoveryLoginActivity::class.java))
            }
    }
}
