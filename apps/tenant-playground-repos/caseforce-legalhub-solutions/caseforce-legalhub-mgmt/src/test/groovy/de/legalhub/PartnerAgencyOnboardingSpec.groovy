package de.legalhub

import de.legalhub.domains.partneragency.PartnerAgencyOnboardingCommand
import de.legalhub.domains.partneragency.PartnerAgencyResponse
import io.micronaut.core.type.Argument
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpStatus
import io.micronaut.http.client.exceptions.HttpClientResponseException

class PartnerAgencyOnboardingSpec extends BaseSpecification {

    void "can onboard a new partner agency with multiple webhook subscriptions"() {
        given:
        def cmd = new PartnerAgencyOnboardingCommand(
            name: "Frankfurt Law Partners",
            alias: "frankfurt-law",
            email: "contact@frankfurt-law.de",
            status: de.legalhub.model.PartnerAgency.Status.ACTIVE,
            webhooks: [
                new PartnerAgencyOnboardingCommand.WebhookSubscriptionItem(
                    targetUrl: "https://api.frankfurt-law.de/webhooks/cases",
                    secret: "whsec_frankfurt_custom_secret",
                    eventTypes: ["LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED"]
                ),
                new PartnerAgencyOnboardingCommand.WebhookSubscriptionItem(
                    targetUrl: "https://api.frankfurt-law.de/webhooks/actions",
                    secret: null, // Should auto-generate
                    eventTypes: ["ACTION_CREATED", "ACTION_UPDATED"]
                )
            ]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/partner-agencies/onboarding", cmd),
            PartnerAgencyResponse
        )

        then:
        response.status() == HttpStatus.CREATED
        def body = response.body()
        body.id != null
        body.alias == "frankfurt-law"
        body.name == "Frankfurt Law Partners"
        body.email == "contact@frankfurt-law.de"
        body.webhooks.size() == 2

        def casesSub = body.webhooks.find { it.targetUrl == "https://api.frankfurt-law.de/webhooks/cases" }
        casesSub != null
        casesSub.secret == "whsec_frankfurt_custom_secret"
        casesSub.eventTypes == ["LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED"]

        def actionsSub = body.webhooks.find { it.targetUrl == "https://api.frankfurt-law.de/webhooks/actions" }
        actionsSub != null
        actionsSub.secret.startsWith("whsec_")
        actionsSub.eventTypes == ["ACTION_CREATED", "ACTION_UPDATED"]
    }

    void "can retrieve newly onboarded partner agency by alias"() {
        given:
        def cmd = new PartnerAgencyOnboardingCommand(
            name: "Munich Advocates",
            alias: "munich-advocates",
            email: "info@munich-advocates.de",
            status: de.legalhub.model.PartnerAgency.Status.ACTIVE,
            webhooks: [
                new PartnerAgencyOnboardingCommand.WebhookSubscriptionItem(
                    targetUrl: "https://munich-advocates.de/webhook",
                    secret: "whsec_munich_123",
                    eventTypes: ["LEGAL_CASE_CREATED"]
                )
            ]
        )
        apiClient.toBlocking().exchange(
            HttpRequest.POST("/partner-agencies/onboarding", cmd),
            PartnerAgencyResponse
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/partner-agencies/by-alias/munich-advocates"),
            PartnerAgencyResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().alias == "munich-advocates"
        response.body().name == "Munich Advocates"
        response.body().webhooks.size() == 1
        response.body().webhooks[0].targetUrl == "https://munich-advocates.de/webhook"
    }

    void "rejects onboarding when alias already exists"() {
        given:
        def cmd1 = new PartnerAgencyOnboardingCommand(
            name: "Cologne Legal Tech",
            alias: "cologne-legal",
            email: "dev@cologne-legal.de",
            status: de.legalhub.model.PartnerAgency.Status.ACTIVE,
            webhooks: []
        )
        apiClient.toBlocking().exchange(
            HttpRequest.POST("/partner-agencies/onboarding", cmd1),
            PartnerAgencyResponse
        )

        when:
        def duplicateCmd = new PartnerAgencyOnboardingCommand(
            name: "Cologne Legal Tech 2",
            alias: "cologne-legal",
            email: "other@cologne-legal.de",
            status: de.legalhub.model.PartnerAgency.Status.ACTIVE,
            webhooks: []
        )
        apiClient.toBlocking().exchange(
            HttpRequest.POST("/partner-agencies/onboarding", duplicateCmd),
            PartnerAgencyResponse
        )

        then:
        def ex = thrown(HttpClientResponseException)
        ex.status == HttpStatus.CONFLICT
    }

    void "can onboard a partner agency with legal cases, lawyer, assignee, and actions, reusing existing users"() {
        given: "A partner agency onboarding command with legal cases, lawyer, assignee, and nested actions"
        def lawyerEmail = "lawyer.huber@hamburg-legal.de"
        def assigneeEmail = "assignee.bauer@hamburg-legal.de"
        def actionAssigneeEmail = "action.clerk@hamburg-legal.de"

        def cmd = new PartnerAgencyOnboardingCommand(
            name: "Hamburg Legal Partners",
            alias: "hamburg-legal",
            email: "contact@hamburg-legal.de",
            status: de.legalhub.model.PartnerAgency.Status.ACTIVE,
            webhooks: [
                new PartnerAgencyOnboardingCommand.WebhookSubscriptionItem(
                    targetUrl: "https://api.hamburg-legal.de/webhooks/all",
                    secret: "whsec_hamburg_sec",
                    eventTypes: ["LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED", "ACTION_CREATED", "ACTION_UPDATED"]
                )
            ],
                legalCases: [
                new de.legalhub.domains.partneragency.LegalCaseOnboardingItem(
                    caseNumber: "CASE-HAM-001",
                    legalField: "Commercial Litigation",
                    status: "OPEN",
                    summary: "Commercial dispute file",
                    lawyer: new de.legalhub.domains.partneragency.UserOnboardingItem(
                        email: lawyerEmail,
                        firstname: "Klaus",
                        lastname: "Huber",
                        password: "SecretHuber123!",
                        enabled: true,
                        roles: ["CASEFORCE", "LEGAL_HERO"]
                    ),
                    assignee: new de.legalhub.domains.partneragency.UserOnboardingItem(
                        email: assigneeEmail,
                        firstname: "Sarah",
                        lastname: "Bauer",
                        password: "SecretBauer123!",
                        enabled: true
                    ),
                    actions: [
                        new de.legalhub.domains.partneragency.ActionOnboardingItem(
                            name: "Review statement of claims",
                            isTask: true,
                            status: "OPEN",
                            assignee: new de.legalhub.domains.partneragency.UserOnboardingItem(
                                email: actionAssigneeEmail,
                                firstname: "Paul",
                                lastname: "Clerk"
                            ),
                            dueDate: java.time.LocalDate.of(2026, 12, 31),
                            notes: "Urgent preliminary review"
                        )
                    ]
                ),
                new de.legalhub.domains.partneragency.LegalCaseOnboardingItem(
                    caseNumber: "CASE-HAM-002",
                    legalField: "Corporate M&A",
                    status: "OPEN",
                    summary: "Cross-border merger case",
                    // Reusing the same lawyer and assignee to verify avoidance of duplicate users
                    lawyer: new de.legalhub.domains.partneragency.UserOnboardingItem(
                        email: lawyerEmail,
                        firstname: "Klaus",
                        lastname: "Huber"
                    ),
                    assignee: new de.legalhub.domains.partneragency.UserOnboardingItem(
                        email: assigneeEmail,
                        firstname: "Sarah",
                        lastname: "Bauer"
                    ),
                    actions: [
                        new de.legalhub.domains.partneragency.ActionOnboardingItem(
                            name: "Draft acquisition agreement",
                            isTask: false,
                            status: "OPEN",
                            assignee: new de.legalhub.domains.partneragency.UserOnboardingItem(
                                email: lawyerEmail
                            )
                        )
                    ]
                )
            ]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/partner-agencies/onboarding", cmd),
            PartnerAgencyResponse
        )

        then:
        response.status() == HttpStatus.CREATED
        def body = response.body()
        body.id != null
        body.alias == "hamburg-legal"
        body.cases.size() == 2

        def case1 = body.cases.find { it.caseNumber == "CASE-HAM-001" }
        case1 != null
        case1.lawyerId != null
        case1.assigneeId != null

        def case2 = body.cases.find { it.caseNumber == "CASE-HAM-002" }
        case2 != null
        case2.lawyerId == case1.lawyerId // Verified: Reused existing user!
        case2.assigneeId == case1.assigneeId // Verified: Reused existing user!
    }

    void "can batch onboard multiple partner agencies with webhooks and cases"() {
        given:
        def batchCmd = new de.legalhub.domains.partneragency.PartnerAgencyBatchOnboardingCommand(
            agencies: [
                new PartnerAgencyOnboardingCommand(
                    name: "Stuttgart Legal Group",
                    alias: "stuttgart-legal",
                    email: "info@stuttgart-legal.de",
                    webhooks: [
                        new PartnerAgencyOnboardingCommand.WebhookSubscriptionItem(
                            targetUrl: "https://stuttgart-legal.de/hook",
                            eventTypes: ["LEGAL_CASE_CREATED"]
                        )
                    ],
                        legalCases: [
                        new de.legalhub.domains.partneragency.LegalCaseOnboardingItem(
                            caseNumber: "CASE-STU-101",
                            legalField: "IP Law",
                            summary: "Patent dispute"
                        )
                    ]
                ),
                new PartnerAgencyOnboardingCommand(
                    name: "Dresden Advocates",
                    alias: "dresden-advocates",
                    email: "contact@dresden-advocates.de",
                    webhooks: [],
                        legalCases: []
                )
            ]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/partner-agencies/batch-onboarding", batchCmd),
            Argument.listOf(PartnerAgencyResponse)
        )

        then:
        response.status() == HttpStatus.CREATED
        response.body().size() == 2
        response.body()[0].alias == "stuttgart-legal"
        response.body()[0].cases.size() == 1
        response.body()[1].alias == "dresden-advocates"
    }
}
