package de.legalhub.domains.webhook

import de.legalhub.model.WebhookSubscription
import de.legalhub.adapters.output.repository.PartnerAgencyRepository
import de.legalhub.adapters.output.repository.WebhookSubscriptionRepository
import io.micronaut.http.HttpStatus
import io.micronaut.http.exceptions.HttpStatusException
import jakarta.inject.Singleton
import jakarta.transaction.Transactional
import java.security.SecureRandom
import java.time.Instant
import java.util.Base64

@Singleton
open class WebhookSubscriptionService(
    private val webhookSubscriptionRepository: WebhookSubscriptionRepository,
    private val partnerAgencyRepository: PartnerAgencyRepository,
    private val urlSecurityValidator: UrlSecurityValidator
) {

    fun get(id: Long): WebhookSubscription? {
        val sub = webhookSubscriptionRepository.findById(id).orElse(null)
        return if (sub?.deletedAt == null) sub else null
    }

    fun list(partnerAgencyId: Long? = null): List<WebhookSubscription> {
        return if (partnerAgencyId != null) {
            webhookSubscriptionRepository.findByPartnerAgencyIdAndDeletedAtIsNull(partnerAgencyId)
        } else {
            webhookSubscriptionRepository.findByDeletedAtIsNull()
        }
    }

    @Transactional
    open fun create(cmd: WebhookSubscriptionCommands.Create): WebhookSubscription {
        val partnerAgencyId = cmd.partnerAgencyId
            ?: throw HttpStatusException(HttpStatus.BAD_REQUEST, "partnerAgencyId is required")
        val targetUrl = cmd.targetUrl
            ?: throw HttpStatusException(HttpStatus.BAD_REQUEST, "targetUrl is required")

        val agency = partnerAgencyRepository.findById(partnerAgencyId)
            .orElseThrow { HttpStatusException(HttpStatus.NOT_FOUND, "PartnerAgency not found: $partnerAgencyId") }

        urlSecurityValidator.validate(targetUrl)

        val secret = if (cmd.secret.isNullOrBlank()) {
            generateSecret()
        } else {
            cmd.secret!!.trim()
        }

        val subscription = WebhookSubscription().apply {
            this.partnerAgency = agency
            this.targetUrl = targetUrl.trim()
            this.secret = secret
            this.eventTypes = if (cmd.eventTypes.isEmpty()) {
                listOf("LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED", "ACTION_CREATED", "ACTION_UPDATED")
            } else {
                cmd.eventTypes
            }
            this.status = WebhookSubscription.Status.ACTIVE
        }

        return webhookSubscriptionRepository.save(subscription)
    }

    @Transactional
    open fun update(id: Long, cmd: WebhookSubscriptionCommands.Update): WebhookSubscription {
        val subscription = get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "WebhookSubscription not found: $id")

        cmd.targetUrl?.let {
            urlSecurityValidator.validate(it)
            subscription.targetUrl = it.trim()
        }
        cmd.secret?.let {
            if (it.isNotBlank()) subscription.secret = it.trim()
        }
        cmd.eventTypes?.let {
            subscription.eventTypes = it
        }
        cmd.status?.let {
            subscription.status = WebhookSubscription.Status.valueOf(it.uppercase())
        }

        return webhookSubscriptionRepository.update(subscription)
    }

    @Transactional
    open fun delete(id: Long) {
        val subscription = get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "WebhookSubscription not found: $id")
        subscription.deletedAt = Instant.now()
        subscription.status = WebhookSubscription.Status.INACTIVE
        webhookSubscriptionRepository.update(subscription)
    }

    private fun generateSecret(): String {
        val randomBytes = ByteArray(24)
        SecureRandom().nextBytes(randomBytes)
        return "whsec_" + Base64.getUrlEncoder().withoutPadding().encodeToString(randomBytes)
    }
}
