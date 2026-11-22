package de.legalhub.domains.webhook

import jakarta.inject.Singleton
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

@Singleton
class WebhookSigner {

    companion object {
        const val HEADER_SIGNATURE = "X-Caseforce-Signature-256"
        const val HEADER_TIMESTAMP = "X-Caseforce-Timestamp"
        const val HEADER_EVENT = "X-Caseforce-Event"
        const val HEADER_DELIVERY_ID = "X-Caseforce-Delivery-Id"
        private const val HMAC_SHA256_ALGORITHM = "HmacSHA256"
        private const val SIGNATURE_PREFIX = "sha256="
    }

    /**
     * Computes HMAC-SHA256 signature for the given payload and timestamp using the partner secret.
     * Signature format: "sha256=<hex_encoded_hash>"
     */
    fun sign(payload: String, timestamp: Long, secret: String): String {
        val message = "$timestamp.$payload"
        val keySpec = SecretKeySpec(secret.toByteArray(Charsets.UTF_8), HMAC_SHA256_ALGORITHM)
        val mac = Mac.getInstance(HMAC_SHA256_ALGORITHM)
        mac.init(keySpec)
        val hmacBytes = mac.doFinal(message.toByteArray(Charsets.UTF_8))
        val hexString = hmacBytes.joinToString("") { "%02x".format(it) }
        return "$SIGNATURE_PREFIX$hexString"
    }

    /**
     * Verifies the signature using constant-time byte comparison to prevent timing attacks.
     */
    fun verify(payload: String, timestamp: Long, secret: String, signatureHeader: String): Boolean {
        val expected = sign(payload, timestamp, secret)
        val expectedBytes = expected.toByteArray(Charsets.UTF_8)
        val actualBytes = signatureHeader.trim().toByteArray(Charsets.UTF_8)
        return MessageDigest.isEqual(expectedBytes, actualBytes)
    }
}
