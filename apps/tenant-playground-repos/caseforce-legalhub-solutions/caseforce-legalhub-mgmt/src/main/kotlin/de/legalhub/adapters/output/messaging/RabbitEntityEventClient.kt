package de.legalhub.adapters.output.messaging

import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.RabbitMQTopics
import io.micronaut.rabbitmq.annotation.Binding
import io.micronaut.rabbitmq.annotation.RabbitClient
import jakarta.validation.Valid

@RabbitClient
interface RabbitEntityEventClient {

    @Binding(RabbitMQTopics.ENTITY_EVENT)
    fun send(@Valid event: EntityEvent)
}
