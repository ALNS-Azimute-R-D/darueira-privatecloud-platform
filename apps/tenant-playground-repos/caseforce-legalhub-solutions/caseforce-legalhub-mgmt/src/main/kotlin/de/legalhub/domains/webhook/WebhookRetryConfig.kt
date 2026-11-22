package de.legalhub.domains.webhook

import io.micronaut.context.annotation.Value
import jakarta.inject.Singleton

@Singleton
class WebhookRetryConfig(
    @Value("\${webhook.retry.max-attempts:3}") val maxAttempts: Int = 3,
    @Value("\${webhook.retry.initial-backoff-ms:1000}") val initialBackoffMs: Long = 1000L,
    @Value("\${webhook.retry.multiplier:2.0}") val multiplier: Double = 2.0,
    @Value("\${webhook.retry.job.enabled:true}") val jobEnabled: Boolean = true,
    @Value("\${webhook.retry.job.fixed-delay:5m}") val jobFixedDelay: String = "5m",
    @Value("\${webhook.retry.job.max-attempts:10}") val jobMaxAttempts: Int = 10
)
