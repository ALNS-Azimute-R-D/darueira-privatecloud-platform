package de.legalhub.adapters.input.messaging

import de.legalhub.domains.webhook.WebhookEntityEventProcessor
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.RabbitMQTopics
import io.micronaut.rabbitmq.annotation.Queue
import io.micronaut.rabbitmq.annotation.RabbitListener
import jakarta.inject.Singleton
import org.slf4j.LoggerFactory

/**
 * Example listener that consumes entity events from RabbitMQ.
 * This demonstrates the pattern for processing events asynchronously.
 */
@Singleton
@RabbitListener
class EntityEventListener(
    private val webhookEntityEventProcessor: WebhookEntityEventProcessor,
) {

    private val log = LoggerFactory.getLogger(EntityEventListener::class.java)

    @Queue(RabbitMQTopics.ENTITY_EVENT)
    fun onEntityEvent(event: EntityEvent) {
        log.info("Received Entity Event: type={}, id={}", event.entityType, event.entityId)

        // Process the event asynchronously
        webhookEntityEventProcessor.processEvent(event)
            .forEach { delivery ->
                log.info("Created Webhook Delivery: id={}, subscriptionId={}", delivery.id, delivery.subscription?.id)
            }
    }
}
