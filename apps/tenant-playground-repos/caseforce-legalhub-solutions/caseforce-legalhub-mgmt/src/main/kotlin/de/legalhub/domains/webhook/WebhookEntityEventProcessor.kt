package de.legalhub.domains.webhook

import de.legalhub.adapters.output.repository.ActionRepository
import de.legalhub.adapters.output.repository.LegalCaseRepository
import de.legalhub.adapters.output.repository.WebhookDeliveryRepository
import de.legalhub.adapters.output.repository.WebhookSubscriptionRepository
import de.legalhub.model.WebhookDelivery
import de.legalhub.model.WebhookSubscription
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import io.micronaut.serde.ObjectMapper
import jakarta.inject.Singleton
import org.slf4j.LoggerFactory
import java.util.*

@Singleton
open class WebhookEntityEventProcessor(
    private val legalCaseRepository: LegalCaseRepository,
    private val actionRepository: ActionRepository,
    private val webhookSubscriptionRepository: WebhookSubscriptionRepository,
    private val webhookDeliveryRepository: WebhookDeliveryRepository,
    private val webhookDeliveryService: WebhookDeliveryService,
    private val objectMapper: ObjectMapper
) {

    private val log = LoggerFactory.getLogger(WebhookEntityEventProcessor::class.java)

    open fun processEvent(event: EntityEvent): List<WebhookDelivery> {

        log.info("Processing Entity Event for WebHooks: type={}, id={}", event.entityType, event.entityId)

        return when (event.entityType) {
            EntityType.LEGAL_CASE -> processLegalCaseEvent(event.entityId)
            EntityType.ACTION -> processActionEvent(event.entityId)
            else -> {
                log.debug("No webhook handler configured for entity type {}", event.entityType)
                emptyList()
            }
        }
    }

    private fun processLegalCaseEvent(caseId: Long): List<WebhookDelivery> {
        val legalCase = legalCaseRepository.findById(caseId).orElse(null) ?: return emptyList()
        val agencyId = legalCase.partnerAgency?.id ?: return emptyList()

        val activeSubscriptions = webhookSubscriptionRepository.findByPartnerAgencyIdAndStatusAndDeletedAtIsNull(
            agencyId,
            WebhookSubscription.Status.ACTIVE
        )

        if (activeSubscriptions.isEmpty()) {
            return emptyList()
        }

        val eventType = "LEGAL_CASE_UPDATED"
        val payloadMap = mapOf(
            "eventId" to UUID.randomUUID().toString(),
            "eventType" to eventType,
            "timestamp" to System.currentTimeMillis(),
            "partnerAgencyId" to agencyId,
            "data" to mapOf(
                "id" to legalCase.id,
                "caseNumber" to legalCase.caseNumber,
                "legalField" to legalCase.legalField,
                "status" to legalCase.status.name,
                "summary" to legalCase.summary,
                "lawyerId" to legalCase.lawyer?.id,
                "assigneeId" to legalCase.assignee?.id,
                "partnerAgencyId" to agencyId,
                "dateCreated" to legalCase.createdAt?.toString(),
                "dateUpdated" to legalCase.updatedAt?.toString()
            )
        )
        val payloadJson = objectMapper.writeValueAsString(payloadMap)

        val createdDeliveries = mutableListOf<WebhookDelivery>()
        for (sub in activeSubscriptions) {
            if (sub.eventTypes.isEmpty() || sub.eventTypes.contains(eventType) || sub.eventTypes.contains("LEGAL_CASE_CREATED")) {
                val delivery = WebhookDelivery().apply {
                    this.subscription = sub
                    this.eventType = eventType
                    this.entityType = "LEGAL_CASE"
                    this.entityId = legalCase.id!!
                    this.payload = payloadJson
                    this.status = WebhookDelivery.Status.PENDING
                }
                val saved = webhookDeliveryRepository.save(delivery)
                webhookDeliveryService.deliverAsync(saved.id!!)
                createdDeliveries.add(saved)
            }
        }
        return createdDeliveries
    }

    private fun processActionEvent(actionId: Long): List<WebhookDelivery> {
        val action = actionRepository.findById(actionId).orElse(null) ?: return emptyList()
        val agencyId = action.legalCase?.partnerAgency?.id ?: return emptyList()

        val activeSubscriptions = webhookSubscriptionRepository.findByPartnerAgencyIdAndStatusAndDeletedAtIsNull(
            agencyId,
            WebhookSubscription.Status.ACTIVE
        )

        if (activeSubscriptions.isEmpty()) {
            return emptyList()
        }

        val eventType = "ACTION_UPDATED"
        val payloadMap = mapOf(
            "eventId" to UUID.randomUUID().toString(),
            "eventType" to eventType,
            "timestamp" to System.currentTimeMillis(),
            "partnerAgencyId" to agencyId,
            "data" to mapOf(
                "id" to action.id,
                "legalCaseId" to action.legalCase?.id,
                "name" to action.name,
                "status" to action.status.name,
                "isTask" to action.isTask,
                "assigneeId" to action.assignee?.id,
                "createdById" to action.createdBy?.id,
                "dueDate" to action.dueDate?.toString(),
                "notes" to action.notes,
                "dateCreated" to action.createdAt?.toString(),
                "dateUpdated" to action.updatedAt?.toString()
            )
        )
        val payloadJson = objectMapper.writeValueAsString(payloadMap)

        val createdDeliveries = mutableListOf<WebhookDelivery>()
        for (sub in activeSubscriptions) {
            if (sub.eventTypes.isEmpty() || sub.eventTypes.contains(eventType) || sub.eventTypes.contains("ACTION_CREATED")) {
                val delivery = WebhookDelivery().apply {
                    this.subscription = sub
                    this.eventType = eventType
                    this.entityType = "ACTION"
                    this.entityId = action.id!!
                    this.payload = payloadJson
                    this.status = WebhookDelivery.Status.PENDING
                }
                val saved = webhookDeliveryRepository.save(delivery)
                webhookDeliveryService.deliverAsync(saved.id!!)
                createdDeliveries.add(saved)
            }
        }
        return createdDeliveries
    }
}
