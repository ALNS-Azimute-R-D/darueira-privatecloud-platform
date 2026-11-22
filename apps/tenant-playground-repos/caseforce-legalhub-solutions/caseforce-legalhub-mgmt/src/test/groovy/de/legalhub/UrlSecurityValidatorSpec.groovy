package de.legalhub

import de.legalhub.domains.webhook.UrlSecurityValidator
import spock.lang.Specification
import spock.lang.Unroll

class UrlSecurityValidatorSpec extends Specification {

    void "accepts valid http and https URLs"() {
        given:
        def validator = new UrlSecurityValidator(true)

        when:
        validator.validate(url)

        then:
        noExceptionThrown()

        where:
        url << [
            "https://api.partner.com/webhook",
            "http://example.com:8080/events",
            "https://webhook.site/1234-5678"
        ]
    }

    @Unroll
    void "rejects invalid URL syntax or scheme: #url"() {
        given:
        def validator = new UrlSecurityValidator(true)

        when:
        validator.validate(url)

        then:
        thrown(IllegalArgumentException)

        where:
        url << [
            "",
            "   ",
            "ftp://files.partner.com/webhook",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "not-a-url"
        ]
    }

    void "rejects cloud metadata endpoints"() {
        given:
        def validator = new UrlSecurityValidator(true)

        when:
        validator.validate("http://169.254.169.254/latest/meta-data/")

        then:
        thrown(IllegalArgumentException)
    }

    void "rejects loopback addresses when private IPs are disallowed"() {
        given:
        def validator = new UrlSecurityValidator(false)

        when:
        validator.validate("http://127.0.0.1:8080/webhook")

        then:
        thrown(IllegalArgumentException)
    }
}
