package de.legalhub.domains.partneragency

import de.legalhub.adapters.output.messaging.RabbitEntityEventClient
import de.legalhub.adapters.output.repository.*
import de.legalhub.domains.legalcase.LegalCaseResponse
import de.legalhub.domains.webhook.UrlSecurityValidator
import de.legalhub.model.*
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import io.micronaut.http.HttpStatus
import io.micronaut.http.exceptions.HttpStatusException
import jakarta.inject.Singleton
import jakarta.transaction.Transactional
import org.slf4j.LoggerFactory
import java.security.SecureRandom
import java.time.Instant
import java.util.*

@Singleton
open class PartnerAgencyService(
    private val partnerAgencyRepository: PartnerAgencyRepository,
    private val webhookSubscriptionRepository: WebhookSubscriptionRepository,
    private val userRepository: UserRepository,
    private val userRoleRepository: UserRoleRepository,
    private val legalCaseRepository: LegalCaseRepository,
    private val actionRepository: ActionRepository,
    private val rabbitEntityEventClient: RabbitEntityEventClient,
    private val urlSecurityValidator: UrlSecurityValidator
) {
    private val log = LoggerFactory.getLogger(PartnerAgencyService::class.java)

    fun get(id: Long): PartnerAgency? {
        val agency = partnerAgencyRepository.findById(id).orElse(null)
        return if (agency?.deletedAt == null) agency else null
    }

    fun getByAlias(alias: String): PartnerAgency? {
        val agency = partnerAgencyRepository.findByAliasAndDeletedAtIsNull(alias.trim().lowercase()).orElse(null)
        return agency
    }

    fun list(): List<PartnerAgency> {
        return partnerAgencyRepository.findByDeletedAtIsNull()
    }

    @Transactional
    open fun onboard(cmd: PartnerAgencyOnboardingCommand): PartnerAgencyResponse {
        val rawAlias = cmd.alias?.trim() ?: ""
        if (rawAlias.isBlank()) {
            throw HttpStatusException(HttpStatus.BAD_REQUEST, "Partner agency alias is required")
        }
        val normalizedAlias = rawAlias.lowercase()

        if (partnerAgencyRepository.existsByAlias(normalizedAlias)) {
            throw HttpStatusException(
                HttpStatus.CONFLICT,
                "Partner agency with alias '$normalizedAlias' already exists"
            )
        }

        // 1. Create and persist Partner Agency
        val agency = PartnerAgency().apply {
            this.name = (cmd.name ?: "").trim()
            this.alias = normalizedAlias
            this.email = cmd.email?.trim()
            this.status = cmd.effectiveStatus()
            this.createdAt = Instant.now()
            this.updatedAt = Instant.now()
        }
        val savedAgency = partnerAgencyRepository.save(agency)

        // 2. Validate and provision initial Webhook Subscriptions
        val savedWebhooks = mutableListOf<WebhookSubscription>()
        for (webhookItem in cmd.allWebhooks()) {
            val targetUrl = (webhookItem.targetUrl ?: "").trim()
            if (targetUrl.isBlank()) continue
            urlSecurityValidator.validate(targetUrl)

            val rawSecret = webhookItem.secret
            val secret = if (rawSecret.isNullOrBlank()) {
                generateSecret()
            } else {
                rawSecret.trim()
            }

            val subscription = WebhookSubscription().apply {
                this.partnerAgency = savedAgency
                this.targetUrl = targetUrl
                this.secret = secret
                this.eventTypes = if (webhookItem.eventTypes.isNullOrEmpty()) {
                    listOf("LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED", "ACTION_CREATED", "ACTION_UPDATED")
                } else {
                    webhookItem.eventTypes!!
                }
                this.status = WebhookSubscription.Status.ACTIVE
                this.createdAt = Instant.now()
                this.updatedAt = Instant.now()
            }

            savedWebhooks.add(webhookSubscriptionRepository.save(subscription))
        }

        // 3. Provision Legal Cases and Actions with User resolution
        val createdCases = mutableListOf<LegalCaseResponse>()
        for (caseItem in cmd.allCases()) {
            val resolvedLawyer = resolveOrCreateUser(caseItem.lawyer)
            val resolvedAssignee = resolveOrCreateUser(caseItem.assignee)

            val caseNumber = if (!caseItem.caseNumber.isNullOrBlank()) {
                caseItem.caseNumber!!.trim()
            } else {
                "CASE-${normalizedAlias.uppercase()}-${UUID.randomUUID().toString().substring(0, 6).uppercase()}"
            }

            val caseStatus = caseItem.status?.let {
                try {
                    CaseStatus.valueOf(it.uppercase())
                } catch (e: Exception) {
                    CaseStatus.OPEN
                }
            } ?: CaseStatus.OPEN

            val existingCaseOpt = legalCaseRepository.findByCaseNumber(caseNumber)
            val savedCase = if (existingCaseOpt.isPresent) {
                val existingCase = existingCaseOpt.get().apply {
                    this.legalField = caseItem.legalField?.trim() ?: this.legalField
                    this.summary = caseItem.summary?.trim() ?: this.summary
                    this.status = caseStatus
                    this.partnerAgency = savedAgency
                    if (resolvedLawyer != null) this.lawyer = resolvedLawyer
                    if (resolvedAssignee != null) this.assignee = resolvedAssignee
                    this.updatedAt = Instant.now()
                }
                legalCaseRepository.update(existingCase)
            } else {
                val newCase = LegalCase().apply {
                    this.caseNumber = caseNumber
                    this.legalField = caseItem.legalField?.trim()
                    this.summary = caseItem.summary?.trim()
                    this.status = caseStatus
                    this.partnerAgency = savedAgency
                    this.lawyer = resolvedLawyer
                    this.assignee = resolvedAssignee
                    this.createdAt = Instant.now()
                    this.updatedAt = Instant.now()
                }
                legalCaseRepository.save(newCase)
            }

            try {
                rabbitEntityEventClient.send(EntityEvent(EntityType.LEGAL_CASE, savedCase.id!!))
            } catch (e: Exception) {
                log.warn("Could not publish LEGAL_CASE event to RabbitMQ: {}", e.message)
            }

            // Provision Actions
            for (actionItem in (caseItem.actions ?: emptyList())) {
                val actionAssignee = resolveOrCreateUser(actionItem.assignee)
                val actionStatus = actionItem.status?.let {
                    try {
                        ActionStatus.valueOf(it.uppercase())
                    } catch (e: Exception) {
                        ActionStatus.OPEN
                    }
                } ?: ActionStatus.OPEN

                val actionName = if (!actionItem.name.isNullOrBlank()) {
                    actionItem.name!!.trim()
                } else {
                    "Action for ${savedCase.caseNumber}"
                }

                val action = Action().apply {
                    this.name = actionName
                    this.isTask = actionItem.isTask ?: false
                    this.status = actionStatus
                    this.legalCase = savedCase
                    this.assignee = actionAssignee
                    this.dueDate = actionItem.dueDate
                    this.notes = actionItem.notes?.trim()
                    this.createdAt = Instant.now()
                    this.updatedAt = Instant.now()
                }
                val savedAction = actionRepository.save(action)

                try {
                    rabbitEntityEventClient.send(EntityEvent(EntityType.ACTION, savedAction.id!!))
                } catch (e: Exception) {
                    log.warn("Could not publish ACTION event to RabbitMQ: {}", e.message)
                }
            }

            createdCases.add(LegalCaseResponse.from(savedCase))
        }

        return PartnerAgencyResponse.from(savedAgency, savedWebhooks, createdCases)
    }

    @Transactional
    open fun onboardBatch(cmd: PartnerAgencyBatchOnboardingCommand): List<PartnerAgencyResponse> {
        return cmd.allAgencies().map { agencyCmd -> onboard(agencyCmd) }
    }

    fun getWithWebhooks(id: Long): PartnerAgencyResponse? {
        val agency = get(id) ?: return null
        val webhooks = webhookSubscriptionRepository.findByPartnerAgencyIdAndDeletedAtIsNull(id)
        val cases = legalCaseRepository.findByPartnerAgencyId(id).map { LegalCaseResponse.from(it) }
        return PartnerAgencyResponse.from(agency, webhooks, cases)
    }

    fun getByAliasWithWebhooks(alias: String): PartnerAgencyResponse? {
        val agency = getByAlias(alias) ?: return null
        val webhooks = webhookSubscriptionRepository.findByPartnerAgencyIdAndDeletedAtIsNull(agency.id!!)
        val cases = legalCaseRepository.findByPartnerAgencyId(agency.id!!).map { LegalCaseResponse.from(it) }
        return PartnerAgencyResponse.from(agency, webhooks, cases)
    }

    private fun resolveOrCreateUser(userItem: UserOnboardingItem?): User? {
        if (userItem == null) return null
        val rawEmail = userItem.email?.trim()
        if (rawEmail.isNullOrBlank()) return null
        val normalizedEmail = rawEmail.lowercase()

        val existingUserOpt = userRepository.findByEmail(normalizedEmail)
        if (existingUserOpt.isPresent) {
            val existingUser = existingUserOpt.get()
            if (existingUser.deletedAt != null) {
                existingUser.deletedAt = null
                existingUser.enabled = true
                existingUser.updatedAt = Instant.now()
                userRepository.update(existingUser)
            }
            return existingUser
        }

        val newUser = User().apply {
            this.email = normalizedEmail
            this.firstname = userItem.firstname?.trim()
            this.lastname = userItem.lastname?.trim()
            this.password = userItem.password ?: "Secret123!"
            this.enabled = userItem.enabled ?: true
            this.createdAt = Instant.now()
            this.updatedAt = Instant.now()
        }
        val savedUser = userRepository.save(newUser)

        val roleStrings = if (!userItem.roles.isNullOrEmpty()) userItem.roles!! else listOf("CASEFORCE")
        for (r in roleStrings.distinct()) {
            val roleEnum = try {
                UserRole.Role.valueOf(r.removePrefix("ROLE_").uppercase())
            } catch (e: Exception) {
                UserRole.Role.CASEFORCE
            }
            userRoleRepository.save(UserRole().apply {
                this.user = savedUser
                this.role = roleEnum
                this.createdAt = Instant.now()
            })
        }

        try {
            rabbitEntityEventClient.send(EntityEvent(EntityType.USER, savedUser.id!!))
        } catch (e: Exception) {
            log.warn("Could not publish USER event to RabbitMQ: {}", e.message)
        }

        return savedUser
    }

    private fun generateSecret(): String {
        val randomBytes = ByteArray(24)
        SecureRandom().nextBytes(randomBytes)
        return "whsec_" + Base64.getUrlEncoder().withoutPadding().encodeToString(randomBytes)
    }
}
