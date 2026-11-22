package de.legalhub.shared.messaging

import com.rabbitmq.client.Channel
import io.micronaut.rabbitmq.connect.ChannelInitializer
import jakarta.inject.Singleton

@Singleton
class RabbitChannelInitializer : ChannelInitializer() {

    override fun initialize(channel: Channel, name: String) {
        // Declare all queues used by the application.
        // Each queue is durable (survives broker restart) and not exclusive/auto-deleted.
        // To add a new queue, simply add another queueDeclare call here.
        channel.queueDeclare(RabbitMQTopics.ENTITY_EVENT, true, false, false, null)
        channel.queueDeclare(RabbitMQTopics.CREATE_ACTION_EVENT, true, false, false, null)
        channel.queueDeclare(RabbitMQTopics.EMAIL_SEND_EVENT, true, false, false, null)
    }
}
