package de.legalhub

import de.legalhub.model.WebhookDelivery
import de.legalhub.model.WebhookSubscription
import de.legalhub.adapters.output.repository.WebhookDeliveryRepository
import de.legalhub.adapters.output.repository.WebhookSubscriptionRepository
import de.legalhub.domains.webhook.WebhookRetryConfig
import de.legalhub.domains.webhook.WebhookRetryScheduledJob
import jakarta.inject.Inject

class WebhookRetryScheduledJobSpec extends BaseSpecification {

    @Inject WebhookSubscriptionRepository webhookSubscriptionRepo
    @Inject WebhookDeliveryRepository webhookDeliveryRepo
    @Inject WebhookRetryScheduledJob retryScheduledJob
    @Inject WebhookRetryConfig retryConfig

    void "scheduled job retries failed webhook deliveries within max attempts threshold"() {
        given: "an active subscription and a failed delivery"
        def sub = webhookSubscriptionRepo.save(new WebhookSubscription(
            partnerAgency: agency,
            targetUrl: "http://localhost:5000/cases",
            secret: "job_test_secret",
            eventTypes: ["LEGAL_CASE_UPDATED"],
            status: WebhookSubscription.Status.ACTIVE
        ))

        def failedDelivery = webhookDeliveryRepo.save(new WebhookDelivery(
            subscription: sub,
            eventType: "LEGAL_CASE_UPDATED",
            entityType: "LEGAL_CASE",
            entityId: 999L,
            payload: '{"test":"scheduled_retry"}',
            status: WebhookDelivery.Status.FAILED,
            attemptCount: 1,
            errorMessage: "Connection refused"
        ))

        and: "another failed delivery that already exceeded jobMaxAttempts"
        def exhaustedDelivery = webhookDeliveryRepo.save(new WebhookDelivery(
            subscription: sub,
            eventType: "LEGAL_CASE_UPDATED",
            entityType: "LEGAL_CASE",
            entityId: 1000L,
            payload: '{"test":"exhausted"}',
            status: WebhookDelivery.Status.FAILED,
            attemptCount: retryConfig.jobMaxAttempts + 1,
            errorMessage: "Permanent failure"
        ))

        when: "the scheduled job processes failed deliveries"
        def retriedCount = retryScheduledJob.processFailedDeliveries()

        then: "only the eligible delivery was retried"
        retriedCount >= 1

        def reloadedFailed = webhookDeliveryRepo.findById(failedDelivery.id).get()
        reloadedFailed.attemptCount > 1

        def reloadedExhausted = webhookDeliveryRepo.findById(exhaustedDelivery.id).get()
        reloadedExhausted.attemptCount == retryConfig.jobMaxAttempts + 1
    }
}
