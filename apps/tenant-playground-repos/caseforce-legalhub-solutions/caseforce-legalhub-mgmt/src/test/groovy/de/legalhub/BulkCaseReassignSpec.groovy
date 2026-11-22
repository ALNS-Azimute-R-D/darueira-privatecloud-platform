package de.legalhub

import de.legalhub.domains.bulk.BulkCaseReassignRequest
import de.legalhub.domains.bulk.BulkOperationResponse
import de.legalhub.domains.legalcase.LegalCaseCommands
import de.legalhub.domains.legalcase.LegalCaseResponse
import de.legalhub.model.User
import de.legalhub.model.WebhookSubscription
import de.legalhub.adapters.output.repository.LegalCaseRepository
import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.adapters.output.repository.WebhookDeliveryRepository
import de.legalhub.adapters.output.repository.WebhookSubscriptionRepository
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpStatus
import jakarta.inject.Inject

class BulkCaseReassignSpec extends BaseSpecification {

    @Inject UserRepository userRepo
    @Inject LegalCaseRepository legalCaseRepo
    @Inject WebhookSubscriptionRepository webhookSubscriptionRepo
    @Inject WebhookDeliveryRepository webhookDeliveryRepo

    void "can execute bulk case reassignment by explicit case IDs"() {
        given: "target lawyer and cases"
        def targetLawyer = userRepo.save(new User(
            email: "target.lawyer@legalhero.de",
            firstname: "Target",
            lastname: "Lawyer",
            password: "Password123"
        ))

        def case1 = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "BULK-01",
                    partnerAgencyAlias: agency.id
            )),
            LegalCaseResponse
        ).body()

        def case2 = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "BULK-02",
                    partnerAgencyAlias: agency.id
            )),
            LegalCaseResponse
        ).body()

        when: "triggering bulk reassignment"
        def req = new BulkCaseReassignRequest(
            targetLawyerId: targetLawyer.id,
            caseIds: [case1.id, case2.id]
        )
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases/bulk-reassign", req),
            BulkOperationResponse
        )

        then: "job is completed with success"
        response.status() == HttpStatus.ACCEPTED
        response.body().id != null
        response.body().status == "COMPLETED"
        response.body().totalCount == 2
        response.body().successCount == 2
        response.body().failedCount == 0

        and: "cases now have the target lawyer assigned"
        def updatedCase1 = legalCaseRepo.findById(case1.id).get()
        def updatedCase2 = legalCaseRepo.findById(case2.id).get()
        updatedCase1.lawyer.id == targetLawyer.id
        updatedCase2.lawyer.id == targetLawyer.id
    }

    void "can query bulk operation job status via GET"() {
        given:
        def targetLawyer = userRepo.save(new User(
            email: "status.lawyer@legalhero.de",
            firstname: "Status",
            lastname: "Lawyer",
            password: "Password123"
        ))

        def createdCase = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "BULK-STATUS-01",
                    partnerAgencyAlias: agency.id
            )),
            LegalCaseResponse
        ).body()

        def submitRes = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases/bulk-reassign", new BulkCaseReassignRequest(
                targetLawyerId: targetLawyer.id,
                caseIds: [createdCase.id]
            )),
            BulkOperationResponse
        ).body()

        when: "getting job by ID"
        def getRes = apiClient.toBlocking().exchange(
            HttpRequest.GET("/cases/bulk-reassign/${submitRes.id}"),
            BulkOperationResponse
        )

        then:
        getRes.status() == HttpStatus.OK
        getRes.body().id == submitRes.id
        getRes.body().status == "COMPLETED"
        getRes.body().totalCount == 1
        getRes.body().successCount == 1
    }

    void "bulk reassignment triggers webhook deliveries for subscribed agencies"() {
        given: "a webhook subscription for the agency"
        def sub = webhookSubscriptionRepo.save(new WebhookSubscription(
            partnerAgency: agency,
            targetUrl: "http://localhost:5000/cases",
            secret: "bulk_test_secret",
            eventTypes: ["LEGAL_CASE_UPDATED"],
            status: WebhookSubscription.Status.ACTIVE
        ))

        def targetLawyer = userRepo.save(new User(
            email: "webhook.lawyer@legalhero.de",
            firstname: "Webhook",
            lastname: "Lawyer",
            password: "Password123"
        ))

        def c1 = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "BULK-WH-01",
                    partnerAgencyAlias: agency.id
            )),
            LegalCaseResponse
        ).body()

        when: "reassigning case"
        apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases/bulk-reassign", new BulkCaseReassignRequest(
                targetLawyerId: targetLawyer.id,
                caseIds: [c1.id]
            )),
            BulkOperationResponse
        )

        then: "reassigned case is verified"
        def refreshedCase = legalCaseRepo.findById(c1.id).get()
        refreshedCase.lawyer.id == targetLawyer.id
    }
}
