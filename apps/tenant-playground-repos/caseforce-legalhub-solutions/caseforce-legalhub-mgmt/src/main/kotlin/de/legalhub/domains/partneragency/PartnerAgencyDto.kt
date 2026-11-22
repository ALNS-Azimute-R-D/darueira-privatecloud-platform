package de.legalhub.domains.partneragency

import de.legalhub.domains.legalcase.LegalCaseResponse
import de.legalhub.domains.webhook.WebhookSubscriptionResponse
import de.legalhub.model.PartnerAgency
import de.legalhub.model.WebhookSubscription
import io.micronaut.serde.annotation.Serdeable
import io.swagger.v3.oas.annotations.media.Schema
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.NotEmpty
import jakarta.validation.constraints.Pattern
import java.time.Instant
import java.time.LocalDate

@Serdeable
data class UserOnboardingItem(
    @field:Schema(description = "User email address", example = "lawyer.schmidt@partner-law.de")
    var email: String? = null,

    @field:Schema(description = "First name", example = "Hans")
    var firstname: String? = null,

    @field:Schema(description = "Last name", example = "Schmidt")
    var lastname: String? = null,

    @field:Schema(description = "Password for newly created user", example = "Secret123!")
    var password: String? = null,

    @field:Schema(description = "Whether the user account is active", example = "true")
    var enabled: Boolean? = true,

    @field:Schema(description = "Roles assigned if user is created", example = "[\"CASEFORCE\", \"LEGAL_HERO\"]")
    var roles: List<String>? = emptyList()
)

@Serdeable
data class ActionOnboardingItem(
    @field:NotBlank
    @field:Schema(description = "Action or task name", example = "Review initial claim documents")
    var name: String? = "",

    @field:Schema(description = "Whether this action is a task", example = "true")
    var isTask: Boolean? = false,

    @field:Schema(description = "Status of the action", example = "OPEN")
    var status: String? = "OPEN",

    @field:Valid
    @field:Schema(description = "Assignee user data (looked up by email or created)")
    var assignee: UserOnboardingItem? = null,

    @field:Schema(description = "Due date in YYYY-MM-DD format", example = "2026-12-31")
    var dueDate: LocalDate? = null,

    @field:Schema(description = "Notes or instructions", example = "Verify partner agency authority")
    var notes: String? = null
)

@Serdeable
data class LegalCaseOnboardingItem(
    @field:Schema(description = "Case number (auto-generated if omitted)", example = "CASE-BER-001")
    var caseNumber: String? = null,

    @field:Schema(description = "Legal domain / field", example = "Corporate Law")
    var legalField: String? = null,

    @field:Schema(description = "Status of the legal case", example = "OPEN")
    var status: String? = "OPEN",

    @field:Schema(description = "Case summary", example = "Corporate litigation file")
    var summary: String? = null,

    @field:Valid
    @field:Schema(description = "Lawyer user data (looked up by email or created)")
    var lawyer: UserOnboardingItem? = null,

    @field:Valid
    @field:Schema(description = "Assignee user data (looked up by email or created)")
    var assignee: UserOnboardingItem? = null,

    @field:Valid
    @field:Schema(description = "Initial collection of actions/tasks for this case")
    var actions: List<ActionOnboardingItem>? = emptyList()
)

@Serdeable
data class PartnerAgencyOnboardingCommand(
    @field:NotBlank
    @field:Schema(description = "Business name of the partner agency", example = "Schmidt & Partner Rechtsanwälte")
    var name: String? = "",

    @field:NotBlank
    @field:Pattern(regexp = "^[a-zA-Z0-9_-]+$", message = "Alias must only contain alphanumeric characters, underscores or hyphens")
    @field:Schema(description = "Unique alphanumeric alias / slug identifier for the agency", example = "schmidt-partner")
    var alias: String? = "",

    @field:Schema(description = "Primary contact email address", example = "contact@schmidt-partner.de")
    var email: String? = null,

    @field:Schema(description = "Status of the partner agency", example = "ACTIVE")
    var status: String? = "ACTIVE",

    @field:Valid
    @field:Schema(description = "Initial collection of webhook subscriptions to provision for this partner agency")
    var webhooks: List<WebhookSubscriptionItem>? = emptyList(),

    @field:Valid
    @field:Schema(description = "Initial collection of legal cases (with lawyer, assignee, and actions) to provision")
    var cases: List<LegalCaseOnboardingItem>? = emptyList(),

    @field:Valid
    var legalCases: List<LegalCaseOnboardingItem>? = emptyList()
) {
    fun allCases(): List<LegalCaseOnboardingItem> = cases?.takeIf { it.isNotEmpty() } ?: legalCases ?: emptyList()
    fun allWebhooks(): List<WebhookSubscriptionItem> = webhooks ?: emptyList()
    fun effectiveStatus(): PartnerAgency.Status {
        return try {
            if (status != null) PartnerAgency.Status.valueOf(status!!.uppercase()) else PartnerAgency.Status.ACTIVE
        } catch (e: Exception) {
            PartnerAgency.Status.ACTIVE
        }
    }

    @Serdeable
    data class WebhookSubscriptionItem(
        @field:NotBlank
        @field:Schema(
            description = "Target HTTP/HTTPS URL for webhook callbacks",
            example = "http://localhost:8085/api/agencies/schmidt-partner/webhooks/caseforce"
        )
        var targetUrl: String? = "",

        @field:Schema(
            description = "Optional custom HMAC secret key. If omitted, a secure random key ('whsec_...') is auto-generated.",
            example = "whsec_customsecret123"
        )
        var secret: String? = null,

        @field:Schema(
            description = "List of event types to subscribe to",
            example = "[\"LEGAL_CASE_CREATED\", \"LEGAL_CASE_UPDATED\", \"ACTION_CREATED\", \"ACTION_UPDATED\"]"
        )
        var eventTypes: List<String>? = listOf("LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED", "ACTION_CREATED", "ACTION_UPDATED")
    )
}

@Serdeable
data class PartnerAgencyBatchOnboardingCommand(
    @field:Valid
    @field:Schema(description = "Collection of partner agencies to onboard in batch")
    var agencies: List<PartnerAgencyOnboardingCommand>? = emptyList()
) {
    fun allAgencies(): List<PartnerAgencyOnboardingCommand> = agencies ?: emptyList()
}

@Serdeable
data class PartnerAgencyResponse(
    var id: Long? = null,
    var alias: String = "",
    var name: String = "",
    var email: String? = null,
    var status: String = "ACTIVE",
    var createdAt: Instant? = null,
    var updatedAt: Instant? = null,
    var webhooks: List<WebhookSubscriptionResponse> = emptyList(),
    var cases: List<LegalCaseResponse> = emptyList(),
    var legalCases: List<LegalCaseResponse> = emptyList()
) {
    companion object {
        fun from(
            agency: PartnerAgency,
            webhooks: List<WebhookSubscription> = emptyList(),
            cases: List<LegalCaseResponse> = emptyList()
        ): PartnerAgencyResponse {
            return PartnerAgencyResponse(
                id = agency.id,
                alias = agency.alias,
                name = agency.name,
                email = agency.email,
                status = agency.status.name,
                createdAt = agency.createdAt,
                updatedAt = agency.updatedAt,
                webhooks = webhooks.map { WebhookSubscriptionResponse.from(it) },
                cases = cases,
                legalCases = cases
            )
        }
    }
}
