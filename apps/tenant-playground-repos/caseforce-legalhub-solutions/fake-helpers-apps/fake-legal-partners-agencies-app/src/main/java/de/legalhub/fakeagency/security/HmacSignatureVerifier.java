package de.legalhub.fakeagency.security;

import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Component
public class HmacSignatureVerifier {

    private static final String HMAC_SHA256 = "HmacSHA256";
    private static final String PREFIX = "sha256=";

    public boolean verify(String payload, Long timestamp, String secret, String signatureHeader) {
        if (payload == null || timestamp == null || secret == null || signatureHeader == null) {
            return false;
        }

        try {
            String message = timestamp + "." + payload;
            SecretKeySpec keySpec = new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), HMAC_SHA256);
            Mac mac = Mac.getInstance(HMAC_SHA256);
            mac.init(keySpec);
            byte[] hmacBytes = mac.doFinal(message.getBytes(StandardCharsets.UTF_8));

            StringBuilder hex = new StringBuilder();
            for (byte b : hmacBytes) {
                hex.append(String.format("%02x", b));
            }
            String expected = PREFIX + hex.toString();

            byte[] expectedBytes = expected.getBytes(StandardCharsets.UTF_8);
            byte[] actualBytes = signatureHeader.trim().getBytes(StandardCharsets.UTF_8);

            return MessageDigest.isEqual(expectedBytes, actualBytes);
        } catch (Exception e) {
            return false;
        }
    }
}
