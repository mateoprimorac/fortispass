package com.fortispass.crypto

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.math.pow

/** RFC 6238 TOTP — TOTP secrets decrypted from vault, never stored plaintext. */
object TOTPEngine {

    enum class Algorithm { SHA1, SHA256, SHA512 }

    fun generateTOTP(
        secret: ByteArray,
        digits: Int = 6,
        period: Int = 30,
        algorithm: Algorithm = Algorithm.SHA1,
        timeMillis: Long = System.currentTimeMillis()
    ): String = hotp(secret, timeMillis / 1000 / period, digits, algorithm)

    fun remainingSeconds(period: Int = 30): Int =
        (period - (System.currentTimeMillis() / 1000) % period).toInt()

    fun decodeBase32(encoded: String): ByteArray {
        val alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        val clean = encoded.uppercase().replace("=", "").replace(" ", "")
        var bits = 0; var count = 0
        val result = mutableListOf<Byte>()
        for (c in clean) {
            val idx = alpha.indexOf(c)
            if (idx < 0) throw IllegalArgumentException("Invalid Base32 char: $c")
            bits = (bits shl 5) or idx; count += 5
            if (count >= 8) { result.add(((bits shr (count - 8)) and 0xFF).toByte()); count -= 8 }
        }
        return result.toByteArray()
    }

    private fun hotp(secret: ByteArray, counter: Long, digits: Int, alg: Algorithm): String {
        val msg = ByteArray(8).also { buf ->
            var c = counter
            for (i in 7 downTo 0) { buf[i] = (c and 0xFF).toByte(); c = c shr 8 }
        }
        val hmacAlg = when (alg) { Algorithm.SHA1 -> "HmacSHA1"; Algorithm.SHA256 -> "HmacSHA256"; Algorithm.SHA512 -> "HmacSHA512" }
        val mac = Mac.getInstance(hmacAlg).apply { init(SecretKeySpec(secret, hmacAlg)) }
        val h = mac.doFinal(msg)
        val offset = h.last().toInt() and 0x0F
        val code = ((h[offset].toInt() and 0x7F) shl 24) or
                ((h[offset+1].toInt() and 0xFF) shl 16) or
                ((h[offset+2].toInt() and 0xFF) shl 8) or
                (h[offset+3].toInt() and 0xFF)
        return (code % 10.0.pow(digits).toInt()).toString().padStart(digits, '0')
    }
}
