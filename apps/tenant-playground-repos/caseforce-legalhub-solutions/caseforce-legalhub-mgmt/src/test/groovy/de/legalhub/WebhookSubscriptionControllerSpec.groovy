package de.legalhub

import de.legalhub.model.ListResult
import de.legalhub.domains.webhook.WebhookSubscriptionCommands
import de.legalhub.domains.webhook.WebhookSubscriptionResponse
import io.micronaut.core.type.Argument
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpStatus
import io.micronaut.http.client.exceptions.HttpClientResponseException

class WebhookSubscriptionControllerSpec extends BaseSpecification {

    void "can register a new webhook subscription"() {
        given:
        def cmd = new WebhookSubscriptionCommands.Create(
            partnerAgencyId: agency.id,
            targetUrl: "https://api.partner.com/caseforce/webhook",
            secret: "custom_partner_secret_123",
            eventTypes: ["LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED"]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/subscriptions", cmd),
            WebhookSubscriptionResponse
        )

        then:
        response.status() == HttpStatus.CREATED
        response.body().id != null
        response.body().partnerAgencyId == agency.id
        response.body().targetUrl == "https://api.partner.com/caseforce/webhook"
        response.body().eventTypes.contains("LEGAL_CASE_CREATED")
        response.body().status == "ACTIVE"
    }

    void "auto-generates secret if omitted in creation request"() {
        given:
        def cmd = new WebhookSubscriptionCommands.Create(
            partnerAgencyId: agency.id,
            targetUrl: "https://auto.partner.com/webhook",
            secret: null,
            eventTypes: []
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/subscriptions", cmd),
            WebhookSubscriptionResponse
        )

        then:
        response.status() == HttpStatus.CREATED
        response.body().id != null
        response.body().eventTypes.size() > 0
    }

    void "can get webhook subscription by id"() {
        given:
        def created = apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/subscriptions", new WebhookSubscriptionCommands.Create(
                partnerAgencyId: agency.id,
                targetUrl: "https://get.partner.com/webhook",
                secret: "test_secret"
            )),
            WebhookSubscriptionResponse
        ).body()

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/webhooks/subscriptions/${created.id}"),
            WebhookSubscriptionResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().id == created.id
        response.body().targetUrl == "https://get.partner.com/webhook"
    }

    void "can list webhook subscriptions for agency"() {
        given:
        apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/subscriptions", new WebhookSubscriptionCommands.Create(
                partnerAgencyId: agency.id,
                targetUrl: "https://list.partner.com/webhook",
                secret: "test_secret"
            )),
            WebhookSubscriptionResponse
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/webhooks/subscriptions?partnerAgencyId=${agency.id}"),
            Argument.of(ListResult, WebhookSubscriptionResponse)
        )

        then:
        response.status() == HttpStatus.OK
        response.body().totalCount >= 1
    }

    void "can update webhook subscription"() {
        given:
        def created = apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/subscriptions", new WebhookSubscriptionCommands.Create(
                partnerAgencyId: agency.id,
                targetUrl: "https://update.partner.com/webhook",
                secret: "test_secret"
            )),
            WebhookSubscriptionResponse
        ).body()

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.PUT("/webhooks/subscriptions/${created.id}", new WebhookSubscriptionCommands.Update(
                targetUrl: "https://updated.partner.com/webhook",
                status: "INACTIVE"
            )),
            WebhookSubscriptionResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().targetUrl == "https://updated.partner.com/webhook"
        response.body().status == "INACTIVE"
    }

    void "can soft delete webhook subscription"() {
        given:
        def created = apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/subscriptions", new WebhookSubscriptionCommands.Create(
                partnerAgencyId: agency.id,
                targetUrl: "https://delete.partner.com/webhook",
                secret: "test_secret"
            )),
            WebhookSubscriptionResponse
        ).body()

        when:
        def deleteResponse = apiClient.toBlocking().exchange(
            HttpRequest.DELETE("/webhooks/subscriptions/${created.id}")
        )

        then:
        deleteResponse.status() == HttpStatus.NO_CONTENT

        when:
        apiClient.toBlocking().exchange(
            HttpRequest.GET("/webhooks/subscriptions/${created.id}"),
            WebhookSubscriptionResponse
        )

        then:
        def ex = thrown(HttpClientResponseException)
        ex.status == HttpStatus.NOT_FOUND
    }

    void "returns 404 when registering subscription for non-existent partner agency"() {
        given:
        def cmd = new WebhookSubscriptionCommands.Create(
            partnerAgencyId: 999999L,
            targetUrl: "https://invalid.partner.com/webhook"
        )

        when:
        apiClient.toBlocking().exchange(
            HttpRequest.POST("/webhooks/subscriptions", cmd),
            WebhookSubscriptionResponse
        )

        then:
        def ex = thrown(HttpClientResponseException)
        ex.status == HttpStatus.NOT_FOUND
    }
}
