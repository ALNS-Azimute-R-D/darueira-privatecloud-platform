package de.legalhub

import de.legalhub.domains.legalcase.LegalCaseCommands
import de.legalhub.domains.legalcase.LegalCaseResponse
import de.legalhub.model.ListResult
import io.micronaut.core.type.Argument
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpStatus

class LegalCaseControllerSpec extends BaseSpecification {

    void "can create a legal case"() {
        given:
        def cmd = new LegalCaseCommands.Create(
            caseNumber: "CASE-001",
            legalField: "RENTAL_LAW",
            summary: "Tenant dispute over deposit",
            partnerAgencyAlias: agency.alias
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", cmd),
            LegalCaseResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().id != null
        response.body().caseNumber == "CASE-001"
        response.body().legalField == "RENTAL_LAW"
        response.body().partnerAgencyId == agency.id
    }

    void "can get a legal case by id"() {
        given:
        def cmd = new LegalCaseCommands.Create(
            caseNumber: "CASE-002",
            legalField: "TRAFFIC_LAW",
            summary: "Speeding ticket dispute",
            partnerAgencyAlias: agency.alias
        )
        def created = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", cmd),
            LegalCaseResponse
        ).body()

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/cases/${created.id}"),
            LegalCaseResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().id == created.id
        response.body().caseNumber == "CASE-002"
    }

    void "can list legal cases"() {
        given:
        apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "CASE-LIST-1",
                partnerAgencyAlias: agency.alias
            )),
            LegalCaseResponse
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/cases"),
            Argument.of(ListResult, LegalCaseResponse)
        )

        then:
        response.status() == HttpStatus.OK
        response.body().totalCount >= 1
    }

    void "can update a legal case"() {
        given:
        def created = apiClient.toBlocking().exchange(
            HttpRequest.POST("/cases", new LegalCaseCommands.Create(
                caseNumber: "CASE-UPD",
                legalField: "RENTAL_LAW",
                partnerAgencyAlias: agency.alias
            )),
            LegalCaseResponse
        ).body()

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.PUT("/cases/${created.id}", new LegalCaseCommands.Update(
                summary: "Updated summary",
                status: "IN_PROGRESS"
            )),
            LegalCaseResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().summary == "Updated summary"
        response.body().status == "IN_PROGRESS"
    }
}
