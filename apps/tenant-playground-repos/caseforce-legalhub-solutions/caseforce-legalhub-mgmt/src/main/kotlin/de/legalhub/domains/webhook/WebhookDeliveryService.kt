package de.legalhub.domains.webhook

import de.legalhub.model.WebhookDelivery
import de.legalhub.adapters.output.repository.WebhookDeliveryRepository
import io.micronaut.http.HttpRequest
import io.micronaut.http.MediaType
import io.micronaut.http.client.HttpClient
import io.micronaut.http.client.annotation.Client
import io.micronaut.http.client.exceptions.HttpClientResponseException
import io.micronaut.scheduling.TaskExecutors
import io.micronaut.scheduling.annotation.Async
import jakarta.inject.Singleton
import jakarta.transaction.Transactional
import org.slf4j.LoggerFactory
import reactor.core.publisher.Mono
import java.time.Duration
import java.time.Instant

@Singleton
open class WebhookDeliveryService(
    private val webhookDeliveryRepository: WebhookDeliveryRepository,
    private val webhookSigner: WebhookSigner,
    @Client("/") private val httpClient: HttpClient,
    private val retryConfig: WebhookRetryConfig
) {

    private val log = LoggerFactory.getLogger(WebhookDeliveryService::class.java)

    fun get(id: Long): WebhookDelivery? {
        return webhookDeliveryRepository.findById(id).orElse(null)
    }

    fun listBySubscription(subscriptionId: Long): List<WebhookDelivery> {
        return webhookDeliveryRepository.findBySubscriptionIdOrderByCreatedAtDesc(subscriptionId)
    }

    @Async(TaskExecutors.BLOCKING)
    open fun deliverAsync(deliveryId: Long) {
        deliverWithAutoRetry(deliveryId)
    }

    open fun deliverWithAutoRetry(deliveryId: Long): WebhookDelivery {
        var delivery = deliver(deliveryId)
        var currentDelay = retryConfig.initialBackoffMs
        val maxRetries = retryConfig.maxAttempts

        while (delivery.status == WebhookDelivery.Status.FAILED && delivery.attemptCount < maxRetries) {
            log.info(
                "Webhook delivery {} failed (attempt {}/{}). Retrying automatically in {}ms with exponential backoff...",
                deliveryId, delivery.attemptCount, maxRetries, currentDelay
            )
            try {
                Thread.sleep(currentDelay)
            } catch (ie: InterruptedException) {
                Thread.currentThread().interrupt()
                log.warn("Auto-retry sleep interrupted for delivery {}", deliveryId)
                break
            }
            currentDelay = (currentDelay * retryConfig.multiplier).toLong()
            delivery = deliver(deliveryId)
        }

        if (delivery.status == WebhookDelivery.Status.FAILED && delivery.attemptCount >= maxRetries) {
            log.warn("Webhook delivery {} exhausted all {} automatic retries. Waiting for scheduled/manual retry fallback.", deliveryId, maxRetries)
        }

        return delivery
    }

    open fun deliver(deliveryId: Long): WebhookDelivery {
        val delivery = webhookDeliveryRepository.findById(deliveryId).orElse(null)
            ?: throw IllegalArgumentException("WebhookDelivery not found: $deliveryId")

        val subscription = delivery.subscription
            ?: throw IllegalStateException("Delivery $deliveryId has no associated subscription")

        val targetUrl = subscription.targetUrl
        val secret = subscription.secret
        val payload = delivery.payload
        val timestamp = System.currentTimeMillis()
        val signature = webhookSigner.sign(payload, timestamp, secret)

        delivery.attemptCount += 1
        delivery.lastAttemptAt = Instant.now()

        try {
            val request = HttpRequest.POST(targetUrl, payload)
                .contentType(MediaType.APPLICATION_JSON_TYPE)
                .header(WebhookSigner.HEADER_SIGNATURE, signature)
                .header(WebhookSigner.HEADER_TIMESTAMP, timestamp.toString())
                .header(WebhookSigner.HEADER_EVENT, delivery.eventType)
                .header(WebhookSigner.HEADER_DELIVERY_ID, delivery.id.toString())

            val response = Mono.from(httpClient.exchange(request, String::class.java))
                .block(Duration.ofSeconds(5))

            val statusCode = response?.status?.code ?: 200
            val body = response?.body()?.take(1000)

            delivery.responseStatusCode = statusCode
            delivery.responseBody = body
            delivery.errorMessage = null
            delivery.status = if (statusCode in 200..299) {
                WebhookDelivery.Status.SUCCESS
            } else {
                WebhookDelivery.Status.FAILED
            }
            log.info("Webhook delivery {} to {} completed with status {}", deliveryId, targetUrl, statusCode)
        } catch (e: HttpClientResponseException) {
            val statusCode = e.status.code
            delivery.responseStatusCode = statusCode
            delivery.responseBody = e.response.getBody(String::class.java).orElse(null)?.take(1000)
            delivery.errorMessage = "HTTP error $statusCode: ${e.message}"
            delivery.status = WebhookDelivery.Status.FAILED
            log.warn("Webhook delivery {} to {} failed with HTTP {}: {}", deliveryId, targetUrl, statusCode, e.message)
        } catch (e: Exception) {
            delivery.responseStatusCode = null
            delivery.errorMessage = "Network / Delivery exception: ${e.message}"
            delivery.status = WebhookDelivery.Status.FAILED
            log.warn("Webhook delivery {} to {} failed: {}", deliveryId, targetUrl, e.message)
        }

        return webhookDeliveryRepository.update(delivery)
    }

    @Transactional
    open fun retry(deliveryId: Long): WebhookDelivery {
        val delivery = webhookDeliveryRepository.findById(deliveryId).orElseThrow {
            IllegalArgumentException("WebhookDelivery not found: $deliveryId")
        }
        delivery.status = WebhookDelivery.Status.PENDING
        webhookDeliveryRepository.update(delivery)
        return deliver(deliveryId)
    }
}
