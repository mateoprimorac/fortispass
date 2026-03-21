package com.fortispass.ui.unlock

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Base64
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.fortispass.R
import com.fortispass.crypto.CryptoEngine
import com.fortispass.crypto.KeyManager
import com.fortispass.databinding.ActivityQrScanBinding
import com.fortispass.network.RelayClient
import com.fortispass.network.ServerTrust
import kotlinx.coroutines.*
import androidx.lifecycle.lifecycleScope
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class QRScanActivity : com.fortispass.ui.BaseActivity() {

    private lateinit var binding: ActivityQrScanBinding
    private val viewModel: UnlockViewModel by viewModels()
    private lateinit var cameraExecutor: ExecutorService
    private var qrProcessed = false

    private val requestPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) startCamera()
        else { toast(getString(R.string.camera_permission_required)); finish() }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityQrScanBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.btnBack.setOnClickListener { finish() }
        cameraExecutor = Executors.newSingleThreadExecutor()

        // When launched without a mode from the Log In Vault menu, it's for scanning an invite QR
        val mode = intent.getStringExtra("mode")
        if (mode == null) {
            binding.tvScanInstruction.setText(R.string.qr_scan_instruction_invite)
        }

        // Tint the viewfinder frame with the current theme accent colour.
        // Layout: FrameLayout[0]=PreviewView, [1]=overlay LinearLayout.
        // The 260dp viewfinder View is the first child of that LinearLayout directly.
        val accentColor = com.fortispass.ui.util.ThemeManager.accentColor(this)
        val strokeColor = (accentColor and 0x00FFFFFF) or 0x88000000.toInt()
        try {
            val overlay = (binding.root as android.view.ViewGroup).getChildAt(1)
                    as? android.view.ViewGroup
            val viewfinderBox = overlay?.getChildAt(0)
            viewfinderBox?.background = android.graphics.drawable.GradientDrawable().apply {
                shape = android.graphics.drawable.GradientDrawable.RECTANGLE
                cornerRadius = 12 * resources.displayMetrics.density
                setStroke((3 * resources.displayMetrics.density).toInt(), strokeColor)
                setColor(android.graphics.Color.TRANSPARENT)
            }
        } catch (_: Exception) { }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED) {
            startCamera()
        } else {
            requestPermission.launch(Manifest.permission.CAMERA)
        }
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.cameraPreview.surfaceProvider)
            }
            val analysis = ImageAnalysis.Builder()
                .setTargetResolution(android.util.Size(1280, 720))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also { it.setAnalyzer(cameraExecutor, QRAnalyzer(::onQRDetected)) }
            try {
                provider.unbindAll()
                provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
                android.util.Log.d("FortispassQR", "Camera bound successfully")
            } catch (e: Exception) {
                android.util.Log.e("FortispassQR", "Camera bind failed", e)
                toast(getString(R.string.err_camera, e.message ?: ""))
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun onQRDetected(raw: String) {
        if (qrProcessed) return
        qrProcessed = true
        // ML Kit callback may fire on a background thread — always handle on main
        if (Thread.currentThread() != mainLooper.thread) {
            qrProcessed = false  // reset before re-entry on main thread
            runOnUiThread { onQRDetected(raw) }
            return
        }

        val payload = runCatching { JSONObject(raw) }.getOrElse {
            toast(getString(R.string.err_invalid_qr)); qrProcessed = false; return
        }

        // Migration import mode — different payload format (v=2)
        if (intent.getStringExtra("mode") == "migration_import") {
            handleMigrationImport(payload)
            return
        }

        // Device invite — join an existing vault
        if (payload.optString("type") == "fp_invite") {
            startActivity(
                Intent(this, com.fortispass.ui.setup.JoinVaultActivity::class.java)
                    .putExtra("invite_payload", raw)
            )
            finish()
            return
        }

        if (payload.optInt("v", -1) != 1) {
            toast(getString(R.string.err_unsupported_qr_version)); qrProcessed = false; return
        }

        val sessionIDBytes = decodeUrlSafe(payload.optString("sid")) ?: run {
            toast(getString(R.string.err_invalid_session_id)); qrProcessed = false; return
        }
        val extEphPub = decodeUrlSafe(payload.optString("epk")) ?: run {
            toast(getString(R.string.err_invalid_pub_key)); qrProcessed = false; return
        }
        val expiry = payload.optLong("exp", 0L)
        val serverSig = decodeUrlSafe(payload.optString("sig")) ?: run {
            toast(getString(R.string.err_invalid_signature)); qrProcessed = false; return
        }
        val relayUrl = payload.optString("url", "")
        if (relayUrl.isEmpty()) { toast(getString(R.string.err_missing_relay_url)); qrProcessed = false; return }

        if (expiry <= System.currentTimeMillis() / 1000) {
            toast(getString(R.string.err_qr_expired)); qrProcessed = false; return
        }

        // Verify server Ed25519 signature against the TOFU-pinned key
        val tsBuf = ByteArray(8).also {
            var x = expiry
            for (i in 7 downTo 0) { it[i] = (x and 0xFF).toByte(); x = x shr 8 }
        }
        val sigMsg = sessionIDBytes + extEphPub + tsBuf

        val pinnedIdentity = ServerTrust.getPinned(this, relayUrl)
        if (pinnedIdentity == null) {
            toast(getString(R.string.err_server_not_trusted))
            qrProcessed = false; return
        }

        // Check the key hasn't changed since we pinned it
        val pinnedPubB64 = pinnedIdentity.pubKeyBase64
        val storedPubB64 = viewModel.getServerPublicKey64()
        if (pinnedPubB64 != storedPubB64) {
            toast(getString(R.string.err_server_key_mismatch_scan))
            qrProcessed = false; return
        }

        if (!CryptoEngine.verify(sigMsg, serverSig, pinnedIdentity.pubKeyBytes)) {
            toast(getString(R.string.err_invalid_server_sig))
            qrProcessed = false; return
        }

        setStatus(getString(R.string.biometric_prompt))
        // Notify relay (and thus the extension) that scan succeeded — extension hides QR
        lifecycleScope.launch(Dispatchers.IO) {
            runCatching {
                val sidB64 = android.util.Base64.encodeToString(sessionIDBytes, android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP)
                RelayClient.ackSession(relayUrl, sidB64)
            } // non-fatal — biometric still proceeds even if ack fails
            withContext(Dispatchers.Main) {
                promptBiometric(sessionIDBytes, extEphPub, relayUrl)
            }
        }
    }

    private fun promptBiometric(sessionIDBytes: ByteArray, extEphPub: ByteArray, relayUrl: String) {
        val iv = KeyManager.getStoredVaultKeyIV(this)
        val cipher = KeyManager.getDecryptCipher(iv)

        val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    result.cryptoObject?.cipher?.let {
                        onBiometricSuccess(it, sessionIDBytes, extEphPub, relayUrl)
                    } ?: toast(getString(R.string.err_biometric_cipher_scan))
                }
                override fun onAuthenticationError(code: Int, msg: CharSequence) {
                    toast(getString(R.string.err_biometric_error, msg))
                    qrProcessed = false
                    setStatus("")
                    // Notify extension that biometric failed/was cancelled
                    val sidB64 = android.util.Base64.encodeToString(sessionIDBytes, android.util.Base64.URL_SAFE or android.util.Base64.NO_WRAP)
                    lifecycleScope.launch(Dispatchers.IO) {
                        runCatching { RelayClient.cancelSession(relayUrl, sidB64, "biometric_failed") }
                    }
                }
                override fun onAuthenticationFailed() { toast(getString(R.string.biometric_not_recognised)) }
            })

        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(getString(R.string.biometric_title))
            .setSubtitle(getString(R.string.biometric_subtitle))
            .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
            .setNegativeButtonText(getString(R.string.cancel))
            .build()
        prompt.authenticate(promptInfo, BiometricPrompt.CryptoObject(cipher))
    }

    private fun onBiometricSuccess(
        cipher: javax.crypto.Cipher,
        sessionIDBytes: ByteArray,
        extEphPub: ByteArray,
        relayUrl: String
    ) {
        setStatus(getString(R.string.status_unlocking))
        lifecycleScope.launch(Dispatchers.IO) {
            var vaultKey: ByteArray? = null
            var sessionKey: ByteArray? = null
            var devEphPriv: ByteArray? = null

            try {
                vaultKey = KeyManager.unwrapVaultKey(cipher, this@QRScanActivity)

                // Generate ephemeral X25519 keypair for this session
                val sod = com.goterl.lazysodium.LazySodiumAndroid(com.goterl.lazysodium.SodiumAndroid())
                val devEphPub = ByteArray(32)
                devEphPriv = ByteArray(32)
                sod.cryptoBoxKeypair(devEphPub, devEphPriv)

                // Derive shared session key (must match extension crypto.js exactly)
                sessionKey = KeyManager.deriveSessionKey(devEphPriv, extEphPub, sessionIDBytes)

                // Encrypt vault key for transit
                val encVaultKey = CryptoEngine.encryptForSession(vaultKey, sessionKey)

                // Sign the response
                val timestamp = System.currentTimeMillis() / 1000
                val signingKey = viewModel.getDeviceSigningKey()
                val sig = CryptoEngine.signSessionResponse(
                    sessionIDBytes, devEphPub, encVaultKey, timestamp, signingKey
                )

                // Session ID must be URL-safe base64 for the API (matches how extension sent it)
                val sessionIDB64 = Base64.encodeToString(sessionIDBytes, Base64.URL_SAFE or Base64.NO_WRAP)

                RelayClient.respondToSession(
                    relayUrl    = relayUrl,
                    sessionID   = sessionIDB64,
                    devEphPub   = devEphPub,
                    encVaultKey = encVaultKey,
                    sig         = sig,
                    deviceID    = viewModel.getDeviceID(),
                    timestamp   = timestamp,
                    authToken   = viewModel.getOrRenewAuthToken()
                )

                withContext(Dispatchers.Main) {
                    setStatus(getString(R.string.status_extension_unlocked))
                    toast(getString(R.string.extension_unlocked_toast))
                    kotlinx.coroutines.delay(1200)
                    finish()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    val msg = e.message ?: ""
                    val isDeviceNotFound = msg.contains("Device not found") || msg.contains("403")
                    val userMsg = if (isDeviceNotFound)
                        getString(R.string.err_device_not_registered)
                    else
                        getString(R.string.err_unlock_failed, msg)

                    setStatus(if (isDeviceNotFound) getString(R.string.err_device_not_registered) else "Failed — $msg")
                    qrProcessed = false

                    if (isDeviceNotFound) {
                        // Show persistent snackbar with Settings shortcut
                        com.google.android.material.snackbar.Snackbar
                            .make(binding.root, userMsg, com.google.android.material.snackbar.Snackbar.LENGTH_INDEFINITE)
                            .setAction(getString(R.string.btn_settings)) {
                                startActivity(android.content.Intent(this@QRScanActivity,
                                    com.fortispass.ui.settings.SettingsActivity::class.java))
                            }
                            .show()
                    } else {
                        toast(userMsg)
                    }
                }
            } finally {
                vaultKey?.fill(0)
                sessionKey?.fill(0)
                devEphPriv?.fill(0)
            }
        }
    }

    private fun handleMigrationImport(payload: org.json.JSONObject) {
        if (payload.optInt("v", -1) != 2) {
            toast(getString(R.string.err_not_migration_qr)); qrProcessed = false; return
        }
        val expiry = payload.optLong("exp", 0L)
        if (expiry <= System.currentTimeMillis() / 1000) {
            toast(getString(R.string.err_migration_qr_expired))
            qrProcessed = false; return
        }
        val relayUrl    = payload.optString("relay_url",    "").ifEmpty { null } ?: run { toast(getString(R.string.err_invalid_migration_qr)); qrProcessed = false; return }
        val authToken   = payload.optString("auth_token",   "").ifEmpty { null } ?: run { toast(getString(R.string.err_invalid_migration_qr)); qrProcessed = false; return }
        val deviceId    = payload.optString("device_id",    "").ifEmpty { null } ?: run { toast(getString(R.string.err_invalid_migration_qr)); qrProcessed = false; return }
        val serverPub   = payload.optString("server_pub",   "").ifEmpty { null } ?: run { toast(getString(R.string.err_invalid_migration_qr)); qrProcessed = false; return }
        val signingKey  = payload.optString("signing_key",  "").ifEmpty { null } ?: run { toast(getString(R.string.err_invalid_migration_qr)); qrProcessed = false; return }
        // migration_id is optional for backwards compatibility — old QR codes without it still import fine, just no auto-wipe
        val migrationId = payload.optString("migration_id", "").ifEmpty { null }

        androidx.appcompat.app.AlertDialog.Builder(this)
            .setTitle(getString(R.string.import_title))
            .setMessage(getString(R.string.import_message))
            .setPositiveButton(getString(R.string.import_confirm)) { _, _ ->
                try {
                    val encPrefs = androidx.security.crypto.EncryptedSharedPreferences.create(
                        this, "fortispass_device",
                        androidx.security.crypto.MasterKey.Builder(this)
                            .setKeyScheme(androidx.security.crypto.MasterKey.KeyScheme.AES256_GCM).build(),
                        androidx.security.crypto.EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                        androidx.security.crypto.EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
                    )
                    encPrefs.edit()
                        .putString("relay_url",        relayUrl)
                        .putString("auth_token",       authToken)
                        .putString("device_id",        deviceId)
                        .putString("server_pub_key",   serverPub)
                        .putString("signing_priv_key", signingKey)
                        .apply()

                    // Pin the server identity so QR scanning works immediately
                    com.fortispass.network.ServerTrust.pinFromMigration(this, relayUrl, serverPub)

                    // Notify the old device to wipe itself — fire and forget, import is already complete
                    if (migrationId != null) {
                        lifecycleScope.launch(Dispatchers.IO) {
                            postMigrationConfirm(relayUrl, authToken, migrationId)
                        }
                    }

                    toast(getString(R.string.import_success))
                    startActivity(android.content.Intent(this, com.fortispass.ui.MainActivity::class.java)
                        .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK or android.content.Intent.FLAG_ACTIVITY_CLEAR_TASK))
                    finish()
                } catch (e: Exception) {
                    toast(getString(R.string.err_import_failed, e.message ?: ""))
                    qrProcessed = false
                }
            }
            .setNegativeButton(getString(R.string.cancel)) { _, _ -> qrProcessed = false }
            .setCancelable(false)
            .show()
    }

    /** POSTs migration confirmation to the relay so the old device can wipe itself. */
    private fun postMigrationConfirm(relayUrl: String, authToken: String, migrationId: String) {
        try {
            val url = java.net.URL("$relayUrl/api/v1/migration/confirm")
            val body = org.json.JSONObject().apply { put("migration_id", migrationId) }.toString().toByteArray()
            val conn = (url.openConnection() as java.net.HttpURLConnection).apply {
                requestMethod = "POST"
                setRequestProperty("Authorization", "Bearer $authToken")
                setRequestProperty("Content-Type", "application/json")
                doOutput = true
                connectTimeout = 8_000
                readTimeout = 8_000
            }
            conn.outputStream.use { it.write(body) }
            conn.responseCode // consume response
            conn.disconnect()
        } catch (_: Exception) { /* best-effort — import already succeeded */ }
    }

    private fun decodeUrlSafe(s: String): ByteArray? =
        runCatching { Base64.decode(s, Base64.URL_SAFE or Base64.NO_WRAP) }.getOrNull()

    private fun setStatus(msg: String) = runOnUiThread {
        binding.tvScanStatus.text = msg
        binding.tvScanStatus.visibility = if (msg.isEmpty()) View.GONE else View.VISIBLE
    }

    private fun toast(msg: String) = runOnUiThread {
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
    }

    override fun onDestroy() { super.onDestroy(); cameraExecutor.shutdown() }
}

class QRAnalyzer(
    private val onResult: (String) -> Unit
) : ImageAnalysis.Analyzer {
    private val scanner = BarcodeScanning.getClient()

    @androidx.camera.core.ExperimentalGetImage
    override fun analyze(proxy: ImageProxy) {
        val mediaImage = proxy.image
        if (mediaImage == null) {
            proxy.close()
            return
        }
        val image = InputImage.fromMediaImage(mediaImage, proxy.imageInfo.rotationDegrees)
        scanner.process(image)
            .addOnSuccessListener { barcodes ->
                android.util.Log.d("FortispassQR", "frames scanned, barcodes=${barcodes.size}")
                val qr = barcodes.firstOrNull { it.format == Barcode.FORMAT_QR_CODE }
                if (qr != null) {
                    android.util.Log.d("FortispassQR", "QR raw value length=${qr.rawValue?.length}")
                    qr.rawValue?.let(onResult)
                }
            }
            .addOnFailureListener { e ->
                android.util.Log.w("FortispassQR", "ML Kit error: ${e.message}")
            }
            .addOnCompleteListener { proxy.close() }
    }
}
