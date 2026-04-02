package com.fortispass.ui.setup

import android.content.Intent
import android.net.Uri
import android.content.res.ColorStateList
import android.os.Bundle
import android.util.Base64
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.fortispass.R
import com.fortispass.crypto.CryptoEngine
import com.fortispass.crypto.KeyManager
import com.fortispass.databinding.ActivitySetupBinding
import com.fortispass.network.RelayClient
import com.fortispass.network.ServerTrust
import com.fortispass.ui.BaseActivity
import com.fortispass.ui.MainActivity
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class SetupActivity : BaseActivity() {

    private lateinit var binding: ActivitySetupBinding

    private var pendingKeys:       KeyManager.DeviceKeys? = null
    private var pendingVaultKey:   ByteArray?             = null
    private var pendingPhrase:     List<String>?          = null
    private var pendingPhraseSeed: ByteArray?             = null
    private var pendingEmptyVault: ByteArray?             = null
    private var pendingRelayUrl:   String                 = ""
    private var pendingDeviceName: String                 = ""
    private var pendingIdentity:   ServerTrust.ServerIdentity? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySetupBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // "pass" is white on dark themes, black on light theme
        if (com.fortispass.ui.util.ThemeManager.getSaved(this) == "light") {
            binding.tvPass.setTextColor(android.graphics.Color.BLACK)
        }

        if (isRegistered()) { goToMain(); return }

        binding.btnRegister.setOnClickListener { startRegistration() }

        // OutlinedButton stroke uses bioColorBorder which is low-contrast in light theme.
        // Resolve bioColorText2 at runtime (adapts to every theme) and apply it as stroke.
        val ta = obtainStyledAttributes(intArrayOf(R.attr.bioColorText2))
        val strokeColor = ColorStateList.valueOf(ta.getColor(0, 0xFF8888A0.toInt()))
        ta.recycle()
        binding.btnLogInVault.strokeColor = strokeColor
        binding.btnSettings.strokeColor = strokeColor

        binding.btnLogInVault.setOnClickListener {
            startActivity(Intent(this, LoginVaultMenuActivity::class.java))
        }
        binding.btnSettings.setOnClickListener {
            startActivity(Intent(this, com.fortispass.ui.settings.SettingsActivity::class.java))
        }
        binding.btnGithub.setOnClickListener {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://github.com/mateoprimorac/fortispass")))
        }
    }

    private fun startRegistration() {
        val relayUrl   = binding.etRelayUrl.text.toString().trim().trimEnd('/')
        val deviceName = binding.etDeviceName.text.toString().trim()

        if (relayUrl.isEmpty()) { toast(getString(R.string.err_enter_url)); return }
        if (deviceName.isEmpty()) { toast(getString(R.string.err_enter_device_name)); return }

        setLoading(true)
        showStatus(getString(R.string.fetching_identity))

        lifecycleScope.launch {
            try {
                val identity = withContext(Dispatchers.IO) { ServerTrust.fetch(relayUrl) }
                val existing = ServerTrust.getPinned(this@SetupActivity, relayUrl)
                if (existing != null) {
                    if (existing.pubKeyBase64 != identity.pubKeyBase64) {
                        showKeyChangedDialog(existing.fingerprint, identity.fingerprint)
                        setLoading(false)
                        return@launch
                    }
                    proceedWithRegistration(relayUrl, deviceName, identity)
                } else {
                    setLoading(false)
                    showTrustDialog(relayUrl, deviceName, identity)
                }
            } catch (e: Exception) {
                setLoading(false)
                showStatus(getString(R.string.err_could_not_reach, e.message ?: ""))
                toast(getString(R.string.err_connection_failed, e.message ?: ""))
            }
        }
    }

    private fun showTrustDialog(relayUrl: String, deviceName: String, identity: ServerTrust.ServerIdentity) {
        val fpLines = identity.fingerprint.split(":").chunked(8)
            .joinToString("\n") { it.joinToString(":") }
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.trust_title))
            .setMessage(getString(R.string.trust_message, relayUrl, fpLines))
            .setPositiveButton(getString(R.string.trust_confirm)) { _, _ ->
                ServerTrust.pin(this, identity)
                setLoading(true)
                lifecycleScope.launch { proceedWithRegistration(relayUrl, deviceName, identity) }
            }
            .setNegativeButton(getString(R.string.cancel)) { _, _ ->
                showStatus(getString(R.string.cancelled))
            }
            .setCancelable(false)
            .show()
    }

    private fun showKeyChangedDialog(pinnedFp: String, newFp: String) {
        val fmt = { fp: String -> fp.split(":").chunked(8).joinToString("\n") { it.joinToString(":") } }
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.key_changed_title))
            .setMessage(getString(R.string.key_changed_message, fmt(pinnedFp), fmt(newFp)))
            .setPositiveButton(getString(R.string.key_changed_confirm)) { _, _ ->
                val relayUrl = binding.etRelayUrl.text.toString().trim().trimEnd('/')
                ServerTrust.clearPin(this, relayUrl)
                startRegistration()
            }
            .setNegativeButton(getString(R.string.cancel)) { _, _ ->
                showStatus(getString(R.string.registration_cancelled))
            }
            .setCancelable(false)
            .show()
    }

    private suspend fun proceedWithRegistration(relayUrl: String, deviceName: String, identity: ServerTrust.ServerIdentity) {
        try {
            showStatus(getString(R.string.generating_keys))
            val keys = withContext(Dispatchers.Default) { KeyManager.generateDeviceKeys() }
            // Derive vault key FROM a generated mnemonic phrase (Option A).
            // The phrase and vault key are two representations of the same 262-bit secret.
            // This makes recovery possible: phrase → vault key, no server-side recovery blob needed.
            val (phrase, vaultKey, phraseSeed) = withContext(Dispatchers.Default) {
                com.fortispass.crypto.MnemonicEngine.generatePhraseAndKey(this@SetupActivity)
            }
            // phrase is displayed after successful registration — hold it in memory until then
            val emptyVault = withContext(Dispatchers.Default) { CryptoEngine.encryptVault(ByteArray(0), vaultKey) }

            showStatus(getString(R.string.registering))
            val result = withContext(Dispatchers.IO) {
                RelayClient.registerDevice(
                    relayUrl = relayUrl, deviceName = deviceName,
                    dhPubKey = keys.dhPublicKey, sigPubKey = keys.signingPublicKey,
                    initialVault = emptyVault,
                    vaultLookupHash = com.fortispass.crypto.MnemonicEngine.vaultLookupHash(vaultKey),
                )
            }

            if (result.serverPubKey.isNotEmpty() && result.serverPubKey != identity.pubKeyBase64) {
                throw SecurityException(getString(R.string.err_server_key_mismatch))
            }

            withContext(Dispatchers.IO) { KeyManager.generateHardwareKey(requireBiometric = true) }

            pendingKeys = keys; pendingVaultKey = vaultKey; pendingPhrase = phrase; pendingPhraseSeed = phraseSeed; pendingEmptyVault = emptyVault
            pendingRelayUrl = relayUrl; pendingDeviceName = deviceName; pendingIdentity = identity

            showStatus(getString(R.string.confirm_biometric))
            withContext(Dispatchers.Main) { promptBiometricForSetup(result.authToken, result.deviceId, identity) }

        } catch (e: Exception) {
            clearPending()
            showStatus(getString(R.string.err_generic, e.message ?: ""))
            toast(getString(R.string.err_registration_failed, e.message ?: ""))
            setLoading(false)
        }
    }

    private fun promptBiometricForSetup(authToken: String, deviceId: String, identity: ServerTrust.ServerIdentity) {
        val cipher = try {
            KeyManager.getEncryptCipher()
        } catch (e: Exception) {
            showStatus(getString(R.string.err_generic, e.message ?: ""))
            toast(getString(R.string.err_cipher_init, e.message ?: ""))
            clearPending(); setLoading(false); return
        }

        val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    val c = result.cryptoObject?.cipher
                    if (c == null) { toast(getString(R.string.err_biometric_cipher)); clearPending(); setLoading(false); return }
                    finishSetup(c, authToken, deviceId, identity)
                }
                override fun onAuthenticationError(code: Int, msg: CharSequence) {
                    toast(getString(R.string.err_biometric_error, msg))
                    showStatus(getString(R.string.biometric_cancelled))
                    clearPending(); setLoading(false)
                }
                override fun onAuthenticationFailed() { toast(getString(R.string.biometric_not_recognised)) }
            })

        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(getString(R.string.secure_vault_title))
            .setSubtitle(getString(R.string.secure_vault_subtitle))
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText(getString(R.string.cancel))
            .build()
        prompt.authenticate(promptInfo, BiometricPrompt.CryptoObject(cipher))
    }

    private fun finishSetup(cipher: javax.crypto.Cipher, authToken: String, deviceId: String, identity: ServerTrust.ServerIdentity) {
        val keys       = pendingKeys       ?: return
        val vaultKey   = pendingVaultKey   ?: return
        val phrase     = pendingPhrase     ?: return
        val phraseSeed = pendingPhraseSeed ?: return

        lifecycleScope.launch {
            try {
                withContext(Dispatchers.Default) { KeyManager.wrapVaultKey(vaultKey.copyOf(), cipher, this@SetupActivity) }
                encryptedPrefs().edit().apply {
                    putString("relay_url",       pendingRelayUrl)
                    putString("auth_token",      authToken)
                    putString("device_id",       deviceId)
                    putString("server_pub_key",  identity.pubKeyBase64)
                    putString("signing_priv_key", Base64.encodeToString(keys.signingPrivateKey, Base64.NO_WRAP))
                    // Store phrase seed so Settings can re-display the real recovery phrase
                    putString("phrase_seed", Base64.encodeToString(phraseSeed, Base64.NO_WRAP))
                    apply()
                }
                keys.signingPrivateKey.fill(0); keys.dhPrivateKey.fill(0)
                clearPending()
                showStatus(getString(R.string.device_registered))
                toast(getString(R.string.setup_complete))
                kotlinx.coroutines.delay(600)
                goToMain()
            } catch (e: Exception) {
                showStatus(getString(R.string.err_generic, e.message ?: ""))
                toast(getString(R.string.err_setup_failed, e.message ?: ""))
                clearPending()
            } finally { setLoading(false) }
        }
    }

    /**
     * Shows the recovery phrase immediately after registration.
     * User must tap "I wrote it down" to proceed to the app.
     * The phrase is shown here once — it can be re-derived later from Settings.
     */
    private fun showSetupPhrase(phrase: List<String>) {
        val dialogView = layoutInflater.inflate(R.layout.dialog_recovery_phrase, null)
        val col1 = dialogView.findViewById<android.widget.LinearLayout>(R.id.ll_col1)
        val col2 = dialogView.findViewById<android.widget.LinearLayout>(R.id.ll_col2)
        val col3 = dialogView.findViewById<android.widget.LinearLayout>(R.id.ll_col3)

        phrase.forEachIndexed { i, word ->
            val tv = android.widget.TextView(this).apply {
                text = "${i + 1}. $word"
                textSize = 13f
                val ta = obtainStyledAttributes(intArrayOf(R.attr.bioColorText))
                setTextColor(ta.getColor(0, android.graphics.Color.WHITE))
                ta.recycle()
                setPadding(0, 4, 0, 4)
            }
            when { i < 8 -> col1.addView(tv); i < 16 -> col2.addView(tv); else -> col3.addView(tv) }
        }

        val dialog = androidx.appcompat.app.AlertDialog.Builder(this)
            .setView(dialogView)
            .setPositiveButton(getString(R.string.recovery_phrase_next)) { _, _ ->
                (phrase as? MutableList)?.clear()
                goToMain()
            }
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

    private fun clearPending() {
        pendingVaultKey?.fill(0)
        pendingPhraseSeed?.fill(0)
        pendingKeys?.signingPrivateKey?.fill(0)
        pendingKeys?.dhPrivateKey?.fill(0)
        pendingKeys = null; pendingVaultKey = null; pendingPhrase = null
        pendingPhraseSeed = null; pendingEmptyVault = null; pendingIdentity = null
    }

    private fun goToMain() {
        startActivity(Intent(this, MainActivity::class.java)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        finish()
    }

    private fun isRegistered(): Boolean = try {
        encryptedPrefs().getString("device_id", null) != null
    } catch (e: Exception) { false }

    private fun encryptedPrefs() = EncryptedSharedPreferences.create(
        this, "fortispass_device",
        MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    private fun setLoading(on: Boolean) {
        binding.btnRegister.isEnabled = !on
        binding.btnRegister.text = if (on) getString(R.string.connecting) else getString(R.string.btn_register)
        binding.etRelayUrl.isEnabled = !on
        binding.etDeviceName.isEnabled = !on
    }

    private fun showStatus(msg: String) = runOnUiThread {
        binding.tvStatus.text = msg
        binding.tvStatus.visibility = View.VISIBLE
    }

    private fun toast(msg: String) = runOnUiThread { Toast.makeText(this, msg, Toast.LENGTH_LONG).show() }
}
