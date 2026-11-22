package de.legalhub

import de.legalhub.domains.webhook.WebhookSigner
import spock.lang.Specification

class WebhookSignerSpec extends Specification {

    WebhookSigner signer = new WebhookSigner()

    void "computes deterministic HMAC-SHA256 signature with sha256= prefix"() {
        given:
        def payload = '{"entityType":"LEGAL_CASE","entityId":1}'
        def timestamp = 1724580000000L
        def secret = "whsec_test_secret_123"

        when:
        def signature = signer.sign(payload, timestamp, secret)

        then:
        signature != null
        signature.startsWith("sha256=")
        signature.length() == 7 + 64 // "sha256=" + 64 hex chars
    }

    void "verifies valid signature successfully"() {
        given:
        def payload = '{"caseNumber":"CASE-001","status":"OPEN"}'
        def timestamp = System.currentTimeMillis()
        def secret = "super_secret_partner_key"
        def validSignature = signer.sign(payload, timestamp, secret)

        expect:
        signer.verify(payload, timestamp, secret, validSignature)
    }

    void "rejects tampered payload"() {
        given:
        def payload = '{"caseNumber":"CASE-001","status":"OPEN"}'
        def tamperedPayload = '{"caseNumber":"CASE-001","status":"CLOSED"}'
        def timestamp = System.currentTimeMillis()
        def secret = "super_secret_partner_key"
        def signature = signer.sign(payload, timestamp, secret)

        expect:
        !signer.verify(tamperedPayload, timestamp, secret, signature)
    }

    void "rejects tampered timestamp"() {
        given:
        def payload = '{"caseNumber":"CASE-001"}'
        def timestamp = 1000L
        def secret = "secret_key"
        def signature = signer.sign(payload, timestamp, secret)

        expect:
        !signer.verify(payload, 2000L, secret, signature)
    }

    void "rejects invalid secret"() {
        given:
        def payload = '{"caseNumber":"CASE-001"}'
        def timestamp = 1000L
        def signature = signer.sign(payload, timestamp, "correct_secret")

        expect:
        !signer.verify(payload, timestamp, "wrong_secret", signature)
    }
}
