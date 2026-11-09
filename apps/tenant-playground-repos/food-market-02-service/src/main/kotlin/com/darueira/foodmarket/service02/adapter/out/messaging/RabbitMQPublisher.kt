package com.darueira.foodmarket.service02.adapter.out.messaging

import com.darueira.foodmarket.service02.domain.model.FoodTradingEvent
import com.darueira.foodmarket.service02.domain.port.out.FoodTradingEventPublisherPort
import com.fasterxml.jackson.databind.ObjectMapper
import com.rabbitmq.client.Channel
import com.rabbitmq.client.Connection
import com.rabbitmq.client.ConnectionFactory
import jakarta.annotation.PostConstruct
import jakarta.annotation.PreDestroy
import jakarta.enterprise.context.ApplicationScoped
import org.eclipse.microprofile.config.inject.ConfigProperty
import org.jboss.logging.Logger

@ApplicationScoped
class RabbitMQPublisher(
    private val objectMapper: ObjectMapper,
    @ConfigProperty(name = "rabbitmq-host", defaultValue = "message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local")
    private val host: String,
    @ConfigProperty(name = "rabbitmq-port", defaultValue = "5672")
    private val port: Int,
    @ConfigProperty(name = "rabbitmq-username", defaultValue = "drr_admin")
    private val user: String,
    @ConfigProperty(name = "rabbitmq-password", defaultValue = "darueira-admin123")
    private val pass: String,
    @ConfigProperty(name = "rabbitmq-virtual-host", defaultValue = "/")
    private val vhost: String,
    @ConfigProperty(name = "app.rabbitmq.topic", defaultValue = "marketplace.foodtrading.topic")
    private val topicExchange: String
) : FoodTradingEventPublisherPort {

    private val log = Logger.getLogger(RabbitMQPublisher::class.java)
    private var connection: Connection? = null
    private var channel: Channel? = null

    @PostConstruct
    fun init() {
        try {
            val factory = ConnectionFactory().apply {
                this.host = this@RabbitMQPublisher.host
                this.port = this@RabbitMQPublisher.port
                this.username = this@RabbitMQPublisher.user
                this.password = this@RabbitMQPublisher.pass
                this.virtualHost = this@RabbitMQPublisher.vhost
            }
            connection = factory.newConnection("quarkus-foodmarket-publisher")
            channel = connection?.createChannel()
            channel?.exchangeDeclare(topicExchange, "topic", true)
            log.infof("[Kotlin/Quarkus 02] Connected RabbitMQ Publisher to exchange: %s", topicExchange)
        } catch (e: Exception) {
            log.warnf("[Kotlin/Quarkus 02] Deferred RabbitMQ Publisher connection: %s", e.message)
        }
    }

    override fun publishEvent(event: FoodTradingEvent) {
        try {
            if (channel == null || !channel!!.isOpen) {
                init()
            }
            val routingKey = "foodtrading.created." + event.marketId.lowercase()
            val payload = objectMapper.writeValueAsBytes(event)
            channel?.basicPublish(topicExchange, routingKey, null, payload)
            log.infof("[Kotlin/Quarkus 02] Published event to RabbitMQ topic %s [%s]: %s", topicExchange, routingKey, event.tradingId)
        } catch (e: Exception) {
            log.errorf("[Kotlin/Quarkus 02] Failed to publish RabbitMQ event: %s", e.message)
        }
    }

    @PreDestroy
    fun cleanup() {
        try {
            channel?.close()
            connection?.close()
        } catch (_: Exception) {}
    }
}
