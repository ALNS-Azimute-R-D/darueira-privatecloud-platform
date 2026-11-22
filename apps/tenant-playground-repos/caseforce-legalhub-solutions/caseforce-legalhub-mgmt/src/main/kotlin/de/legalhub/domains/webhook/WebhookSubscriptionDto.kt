package de.legalhub.domains.webhook

import de.legalhub.model.WebhookSubscription
import io.micronaut.serde.annotation.Serdeable
import java.time.Instant

object WebhookSubscriptionCommands {

    @Serdeable
    data class Create(
        var partnerAgencyId: Long? = null,
        var targetUrl: String? = null,
        var secret: String? = null,
        var eventTypes: List<String> = emptyList()
    )

    @Serdeable
    data class Update(
        var targetUrl: String? = null,
        var secret: String? = null,
        var eventTypes: List<String>? = null,
        var status: String? = null
    )
}

@Serdeable
data class WebhookSubscriptionResponse(
    var id: Long? = null,
    var partnerAgencyId: Long? = null,
    var targetUrl: String? = null,
    var secret: String? = null,
    var eventTypes: List<String> = emptyList(),
    var status: String? = null,
    var dateCreated: Instant? = null,
    var dateUpdated: Instant? = null
) {
    companion object {
        fun from(entity: WebhookSubscription): WebhookSubscriptionResponse {
            return WebhookSubscriptionResponse(
                id = entity.id,
                partnerAgencyId = entity.partnerAgency?.id,
                targetUrl = entity.targetUrl,
                secret = entity.secret,
                eventTypes = entity.eventTypes,
                status = entity.status.name,
                dateCreated = entity.createdAt,
                dateUpdated = entity.updatedAt
            )
        }
    }
}
