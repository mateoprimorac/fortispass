package com.fortispass.ui.unlock

import com.fortispass.R

import android.os.Bundle
import android.util.Base64
import android.widget.Toast
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.fortispass.databinding.ActivityQrScanBinding
import kotlinx.coroutines.*
import androidx.lifecycle.lifecycleScope
import org.json.JSONObject
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/**
 * Scan the browser extension's pairing QR and send an auth token back.
 * QR payload: { v:2, type:"pair", pid:<base64url>, url:<relay>, exp:<ts> }
 *
 * NOTE: Pairing is a stub — the full pairing flow is not yet implemented.
 * This activity correctly reads auth_token from EncryptedSharedPreferences.
 */
@ExperimentalGetImage
class PairExtensionActivity : com.fortispass.ui.BaseActivity() {

    private lateinit var binding: ActivityQrScanBinding
    private lateinit var cameraExecutor: ExecutorService
    private var qrProcessed = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityQrScanBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.btnBack.setOnClickListener { finish() }
        cameraExecutor = Executors.newSingleThreadExecutor()
        startCamera()
    }

    private fun startCamera() {
        val future = ProcessCameraProvider.getInstance(this)
        future.addListener({
            val provider = future.get()
            val preview  = Preview.Builder().build().also {
                it.setSurfaceProvider(binding.cameraPreview.surfaceProvider)
            }
            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .also { it.setAnalyzer(cameraExecutor, QRAnalyzer(::onQRDetected)) }
            provider.unbindAll()
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
        }, ContextCompat.getMainExecutor(this))
    }

    private fun onQRDetected(raw: String) {
        if (qrProcessed) return
        qrProcessed = true

        val payload = runCatching { JSONObject(raw) }.getOrElse {
            toast(getString(R.string.err_invalid_qr_code)); qrProcessed = false; return
        }

        if (payload.optInt("v") != 2 || payload.optString("type") != "pair") {
            toast(getString(R.string.err_not_pairing_qr))
            qrProcessed = false; return
        }

        val expiry = payload.optLong("exp", 0L)
        if (expiry < System.currentTimeMillis() / 1000) {
            toast(getString(R.string.err_qr_expired_pair)); qrProcessed = false; return
        }

        val relayUrl = payload.optString("url", "")
        if (relayUrl.isEmpty()) { toast(getString(R.string.err_missing_relay_url_pair)); qrProcessed = false; return }

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // FIX: read from EncryptedSharedPreferences, not plain SharedPreferences
                val authToken = encryptedPrefs().getString("auth_token", null)
                    ?: error("Not registered — complete setup first")

                // TODO: implement full pairing flow
                withContext(Dispatchers.Main) {
                    toast(getString(R.string.pairing_coming_soon))
                    setResult(RESULT_OK)
                    finish()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    toast(getString(R.string.err_pairing_failed, e.message ?: ""))
                    qrProcessed = false
                }
            }
        }
    }

    private fun encryptedPrefs() = EncryptedSharedPreferences.create(
        this, "fortispass_device",
        MasterKey.Builder(this).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )

    private fun toast(msg: String) =
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show()

    override fun onDestroy() { super.onDestroy(); cameraExecutor.shutdown() }
}
