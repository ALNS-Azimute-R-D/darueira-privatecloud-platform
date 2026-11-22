package de.legalhub

import de.legalhub.domains.legalcase.LegalCaseCommands
import de.legalhub.domains.legalcase.LegalCaseResponse
import de.legalhub.domains.webhook.WebhookDeliveryResponse
import de.legalhub.domains.webhook.WebhookDeliveryService
import de.legalhub.domains.webhook.WebhookEntityEventProcessor
import de.legalhub.domains.webhook.WebhookSigner
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import de.legalhub.model.ListResult
import de.legalhub.model.WebhookSubscription
import de.legalhub.adapters.output.repository.WebhookDeliveryRepository
import de.legalhub.adapters.output.repository.WebhookSubscriptionRepository
import io.micronaut.core.type.Argument
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpStatus
import jakarta.inject.Inject

class WebhookDeliverySpec extends BaseSpecification {

    @Inject WebhookSubscriptionRepository webhookSubscriptionRepo
    @Inject WebhookDeliveryRepository webhookDeliveryRepo
    @Inject WebhookEntityEventProcessor eventListener
    @Inject WebhookDeliveryService webhookDeliveryService
    @Inject WebhookSigner webhookSigner

    void "entity event creates webhook delivery and dispatches payload"() {
        given:
        def sub = webhookSubscriptionRepo.save(new WebhookSubscription(
            partnerAgency: agency,
            targetUrl: "http://localhost:5000/cases", // mock target URL
            secret: "my_test_signing_secret",
            eventTypes: ["LEGAL_CASE_UPDATED"],
            status: WebhookSubscription.Status.ACTIVE
        ))

        and: "a legal case is created"
        def caseRes = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "CASE-DELIV-01",
                legalField: "RENTAL_LAW",
                summary: "Testing delivery flow",
                    partnerAgencyAlias: agency.alias
            )),
            LegalCaseResponse
        ).body()

        when: "event listener processes the entity event"
        def deliveries = eventListener.processEvent(new EntityEvent(EntityType.LEGAL_CASE, caseRes.id))

        then: "a delivery record is created and recorded in DB"
        deliveries.size() == 1
        def delivery = webhookDeliveryRepo.findById(deliveries[0].id).get()
        delivery.subscription.id == sub.id
        delivery.eventType == "LEGAL_CASE_UPDATED"
        delivery.entityType == "LEGAL_CASE"
        delivery.entityId == caseRes.id
        delivery.payload.contains("CASE-DELIV-01")
        delivery.payload.contains(agency.id.toString())

        and: "HMAC signature can be verified using the subscription secret"
        def timestamp = System.currentTimeMillis()
        def signature = webhookSigner.sign(delivery.payload, timestamp, sub.secret)
        webhookSigner.verify(delivery.payload, timestamp, sub.secret, signature)
    }

    void "can query delivery logs via REST API"() {
        given:
        def sub = webhookSubscriptionRepo.save(new WebhookSubscription(
            partnerAgency: agency,
            targetUrl: "http://localhost:5000/cases",
            secret: "query_test_secret",
            eventTypes: ["LEGAL_CASE_UPDATED"],
            status: WebhookSubscription.Status.ACTIVE
        ))

        def caseRes = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "CASE-LOG-01",
                    partnerAgencyAlias: agency.alias
            )),
            LegalCaseResponse
        ).body()

        def deliveries = eventListener.processEvent(new EntityEvent(EntityType.LEGAL_CASE, caseRes.id))
        def delivery = deliveries.find { it.subscription?.id == sub.id }
        def deliveryId = delivery.id

        when: "getting delivery by id"
        def getResponse = apiClient.toBlocking().exchange(
            HttpRequest.GET("/webhooks/deliveries/${deliveryId}"),
                WebhookDeliveryResponse
        )

        then:
        getResponse.status() == HttpStatus.OK
        getResponse.body().id == deliveryId
        getResponse.body().subscriptionId == sub.id
        getResponse.body().eventType == "LEGAL_CASE_UPDATED"

        when: "listing deliveries by subscription id"
        def listResponse = apiClient.toBlocking().exchange(
            HttpRequest.GET("/webhooks/deliveries?subscriptionId=${sub.id}"),
            Argument.of(ListResult, WebhookDeliveryResponse)
        )

        then:
        listResponse.status() == HttpStatus.OK
        listResponse.body().totalCount >= 1
    }

    void "can manually retry a delivery attempt via REST API"() {
        given:
        def sub = webhookSubscriptionRepo.save(new WebhookSubscription(
            partnerAgency: agency,
            targetUrl: "http://localhost:5000/cases",
            secret: "retry_test_secret",
            eventTypes: ["LEGAL_CASE_UPDATED"],
            status: WebhookSubscription.Status.ACTIVE
        ))

        def caseRes = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "CASE-RETRY-01",
                    partnerAgencyAlias: agency.alias
            )),
            LegalCaseResponse
        ).body()

        def deliveries = eventListener.processEvent(new EntityEvent(EntityType.LEGAL_CASE, caseRes.id))
        def delivery = deliveries.find { it.subscription?.id == sub.id }
        def deliveryId = delivery.id

        when: "retrying delivery via POST /webhooks/deliveries/{id}/retry"
        def retryResponse = apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/deliveries/${deliveryId}/retry", [:]),
            WebhookDeliveryResponse
        )

        then:
        retryResponse.status() == HttpStatus.OK
        retryResponse.body().id == deliveryId
        retryResponse.body().attemptCount >= 1
    }
}
