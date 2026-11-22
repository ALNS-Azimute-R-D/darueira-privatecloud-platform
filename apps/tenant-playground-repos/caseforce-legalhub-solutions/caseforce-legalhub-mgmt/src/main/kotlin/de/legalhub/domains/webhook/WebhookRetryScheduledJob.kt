package de.legalhub.domains.webhook

import de.legalhub.model.WebhookDelivery
import de.legalhub.adapters.output.repository.WebhookDeliveryRepository
import io.micronaut.context.annotation.Requires
import io.micronaut.scheduling.annotation.Scheduled
import jakarta.inject.Singleton
import org.slf4j.LoggerFactory

@Singleton
@Requires(property = "webhook.retry.job.enabled", notEquals = "false", defaultValue = "true")
open class WebhookRetryScheduledJob(
    private val webhookDeliveryRepository: WebhookDeliveryRepository,
    private val webhookDeliveryService: WebhookDeliveryService,
    private val retryConfig: WebhookRetryConfig
) {

    private val log = LoggerFactory.getLogger(WebhookRetryScheduledJob::class.java)

    @Scheduled(
        fixedDelay = "\${webhook.retry.job.fixed-delay:5m}",
        initialDelay = "\${webhook.retry.job.initial-delay:1m}"
    )
    open fun processFailedDeliveries(): Int {
        log.info("Running scheduled job to retry failed webhook deliveries...")
        val failedDeliveries = webhookDeliveryRepository.findByStatus(WebhookDelivery.Status.FAILED)
            .filter { it.attemptCount < retryConfig.jobMaxAttempts }

        if (failedDeliveries.isEmpty()) {
            log.debug("No eligible failed webhook deliveries found for scheduled retry.")
            return 0
        }

        log.info(
            "Found {} failed webhook deliveries to retry (attemptCount < {}).",
            failedDeliveries.size,
            retryConfig.jobMaxAttempts
        )

        var retriedCount = 0
        for (delivery in failedDeliveries) {
            val deliveryId = delivery.id ?: continue
            try {
                log.info("Scheduled retry executing for webhook delivery id={}", deliveryId)
                webhookDeliveryService.retry(deliveryId)
                retriedCount++
            } catch (e: Exception) {
                log.error("Scheduled retry failed for delivery id={}: {}", deliveryId, e.message)
            }
        }
        return retriedCount
    }
}
