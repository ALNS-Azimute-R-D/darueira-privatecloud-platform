package de.legalhub.domains.webhook

import io.micronaut.context.annotation.Value
import jakarta.inject.Singleton
import java.net.InetAddress
import java.net.URI

@Singleton
class UrlSecurityValidator(
    @Value("\${caseforce.webhooks.allow-private-ips:true}")
    private val allowPrivateIps: Boolean = true
) {

    /**
     * Validates that the provided webhook target URL is well-formed, uses http/https,
     * and does not attempt SSRF against sensitive internal endpoints when private IPs are blocked.
     */
    fun validate(urlString: String) {
        val trimmed = urlString.trim()
        if (trimmed.isBlank()) {
            throw IllegalArgumentException("Target URL cannot be blank")
        }

        val uri = try {
            URI(trimmed)
        } catch (e: Exception) {
            throw IllegalArgumentException("Invalid URL syntax: $trimmed", e)
        }

        val scheme = uri.scheme?.lowercase()
        if (scheme != "http" && scheme != "https") {
            throw IllegalArgumentException("Invalid URL scheme '$scheme'. Only HTTP and HTTPS are supported.")
        }

        val host = uri.host
        if (host.isNullOrBlank()) {
            throw IllegalArgumentException("Target URL must have a valid host")
        }

        // Check for common cloud metadata endpoints
        if (host == "169.254.169.254" || host == "metadata.google.internal") {
            throw IllegalArgumentException("Target URL cannot point to cloud metadata service: $host")
        }

        if (!allowPrivateIps) {
            try {
                val addresses = InetAddress.getAllByName(host)
                for (addr in addresses) {
                    if (addr.isLoopbackAddress) {
                        throw IllegalArgumentException("Target URL cannot point to loopback address: $host")
                    }
                    if (addr.isLinkLocalAddress) {
                        throw IllegalArgumentException("Target URL cannot point to link-local address: $host")
                    }
                    if (addr.isSiteLocalAddress) {
                        throw IllegalArgumentException("Target URL cannot point to private network address: $host")
                    }
                    if (addr.isAnyLocalAddress) {
                        throw IllegalArgumentException("Target URL cannot point to wildcard local address: $host")
                    }
                }
            } catch (e: IllegalArgumentException) {
                throw e
            } catch (e: Exception) {
                throw IllegalArgumentException("Failed to resolve host '$host': ${e.message}", e)
            }
        }
    }
}
