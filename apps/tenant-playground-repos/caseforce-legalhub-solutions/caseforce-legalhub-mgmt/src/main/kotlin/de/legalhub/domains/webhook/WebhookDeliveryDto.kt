package de.legalhub.domains.webhook

import de.legalhub.model.WebhookDelivery
import io.micronaut.serde.annotation.Serdeable
import java.time.Instant

@Serdeable
data class WebhookDeliveryResponse(
    var id: Long? = null,
    var subscriptionId: Long? = null,
    var eventType: String? = null,
    var entityType: String? = null,
    var entityId: Long? = null,
    var payload: String? = null,
    var status: String? = null,
    var attemptCount: Int = 0,
    var lastAttemptAt: Instant? = null,
    var responseStatusCode: Int? = null,
    var responseBody: String? = null,
    var errorMessage: String? = null,
    var dateCreated: Instant? = null,
    var dateUpdated: Instant? = null
) {
    companion object {
        fun from(entity: WebhookDelivery): WebhookDeliveryResponse {
            return WebhookDeliveryResponse(
                id = entity.id,
                subscriptionId = entity.subscription?.id,
                eventType = entity.eventType,
                entityType = entity.entityType,
                entityId = entity.entityId,
                payload = entity.payload,
                status = entity.status.name,
                attemptCount = entity.attemptCount,
                lastAttemptAt = entity.lastAttemptAt,
                responseStatusCode = entity.responseStatusCode,
                responseBody = entity.responseBody,
                errorMessage = entity.errorMessage,
                dateCreated = entity.createdAt,
                dateUpdated = entity.updatedAt
            )
        }
    }
}
