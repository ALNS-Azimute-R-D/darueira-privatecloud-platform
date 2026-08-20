package com.darueira.foodmarket.service02.adapter.`in`.messaging

import com.darueira.foodmarket.service02.domain.model.FoodTradingEvent
import com.darueira.foodmarket.service02.domain.port.`in`.FoodTradingUseCase
import com.fasterxml.jackson.databind.ObjectMapper
import com.rabbitmq.client.Channel
import com.rabbitmq.client.Connection
import com.rabbitmq.client.ConnectionFactory
import com.rabbitmq.client.DeliverCallback
import io.quarkus.runtime.StartupEvent
import jakarta.annotation.PreDestroy
import jakarta.enterprise.context.ApplicationScoped
import jakarta.enterprise.event.Observes
import org.eclipse.microprofile.config.inject.ConfigProperty
import org.jboss.logging.Logger
import java.util.concurrent.Executors

@ApplicationScoped
class RabbitMQConsumer(
    private val useCase: FoodTradingUseCase,
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
    private val topicExchange: String,
    @ConfigProperty(name = "app.rabbitmq.queue", defaultValue = "marketplace.foodtrading.queue02")
    private val queueName: String
) {

    private val log = Logger.getLogger(RabbitMQConsumer::class.java)
    private var connection: Connection? = null
    private var channel: Channel? = null
    private val executor = Executors.newSingleThreadExecutor()

    fun onStart(@Observes ev: StartupEvent) {
        executor.submit {
            startConsumer()
        }
    }

    private fun startConsumer() {
        var retries = 0
        while (retries < 15) {
            try {
                val factory = ConnectionFactory().apply {
                    this.host = this@RabbitMQConsumer.host
                    this.port = this@RabbitMQConsumer.port
                    this.username = this@RabbitMQConsumer.user
                    this.password = this@RabbitMQConsumer.pass
                    this.virtualHost = this@RabbitMQConsumer.vhost
                }
                connection = factory.newConnection("quarkus-foodmarket-consumer")
                channel = connection?.createChannel()
                channel?.exchangeDeclare(topicExchange, "topic", true)
                channel?.queueDeclare(queueName, true, false, false, null)
                channel?.queueBind(queueName, topicExchange, "#")

                val deliverCallback = DeliverCallback { _, delivery ->
                    val body = String(delivery.body, Charsets.UTF_8)
                    log.infof("[Kotlin/Quarkus 02] Consumed message from queue %s: %s", queueName, body)
                    try {
                        val event = objectMapper.readValue(body, FoodTradingEvent::class.java)
                        useCase.processIncomingEvent(event)
                    } catch (e: Exception) {
                        log.errorf("[Kotlin/Quarkus 02] Failed to deserialize or process message: %s", e.message)
                    }
                }

                channel?.basicConsume(queueName, true, deliverCallback) { _ -> }
                log.infof("[Kotlin/Quarkus 02] RabbitMQ Consumer listening on queue: %s", queueName)
                break
            } catch (e: Exception) {
                retries++
                log.warnf("[Kotlin/Quarkus 02] Retrying RabbitMQ Consumer connection in 2s (%d/15): %s", retries, e.message)
                Thread.sleep(2000)
            }
        }
    }

    @PreDestroy
    fun cleanup() {
        try {
            channel?.close()
            connection?.close()
            executor.shutdown()
        } catch (_: Exception) {}
    }
}
