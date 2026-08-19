package com.darueira.foodmarket.service02.application.service

import com.darueira.foodmarket.service02.domain.model.CreateFoodTradingCommand
import com.darueira.foodmarket.service02.domain.model.FoodTrading
import com.darueira.foodmarket.service02.domain.model.FoodTradingEvent
import com.darueira.foodmarket.service02.domain.port.`in`.FoodTradingUseCase
import com.darueira.foodmarket.service02.domain.port.out.FoodTradingEventPublisherPort
import com.darueira.foodmarket.service02.domain.port.out.FoodTradingPersistencePort
import com.darueira.foodmarket.service02.domain.port.out.FoodTradingSseBroadcasterPort
import io.smallrye.mutiny.Multi
import jakarta.enterprise.context.ApplicationScoped
import org.eclipse.microprofile.config.inject.ConfigProperty
import org.jboss.logging.Logger
import java.math.BigDecimal
import java.time.Instant
import java.util.UUID

@ApplicationScoped
class FoodTradingApplicationService(
    private val persistencePort: FoodTradingPersistencePort,
    private val publisherPort: FoodTradingEventPublisherPort,
    private val sseBroadcasterPort: FoodTradingSseBroadcasterPort,
    @ConfigProperty(name = "app.market-id", defaultValue = "MKT-EU-02-QUARKUS")
    private val marketId: String
) : FoodTradingUseCase {

    private val log = Logger.getLogger(FoodTradingApplicationService::class.java)

    override fun createTrading(command: CreateFoodTradingCommand): FoodTrading {
        log.infof("[Kotlin/Quarkus 02] Creating food trading: %s by %s", command.itemName, command.traderName)

        val trading = FoodTrading(
            marketId = marketId,
            itemName = command.itemName,
            quantity = command.quantity,
            unitPrice = command.unitPrice,
            traderName = command.traderName,
            status = "CONFIRMED",
            createdAt = Instant.now()
        )
        trading.validateAndCalculate()

        // 1. Persist to PostgreSQL (F02)
        val saved = persistencePort.save(trading)

        // 2. Publish to RabbitMQ Topic (F03)
        val event = FoodTradingEvent(
            eventId = UUID.randomUUID().toString(),
            eventType = "FOOD_TRADING_CREATED",
            tradingId = saved.tradingId!!,
            marketId = saved.marketId,
            itemName = saved.itemName,
            quantity = saved.quantity,
            unitPrice = saved.unitPrice,
            totalPrice = saved.totalPrice!!,
            traderName = saved.traderName,
            status = saved.status,
            timestamp = Instant.now()
        )
        publisherPort.publishEvent(event)

        // 3. Broadcast to SSE (F01.3 / F04.2.3)
        sseBroadcasterPort.broadcast(saved)

        return saved
    }

    override fun listTradings(): List<FoodTrading> {
        return persistencePort.findAll()
    }

    override fun subscribeStream(): Multi<FoodTrading> {
        return sseBroadcasterPort.stream()
    }

    override fun processIncomingEvent(event: FoodTradingEvent) {
        log.infof("[Kotlin/Quarkus 02] Processing RabbitMQ consumed event: %s", event.tradingId)

        // Validation
        if (event.quantity <= BigDecimal.ZERO || event.unitPrice <= BigDecimal.ZERO) {
            log.warnf("Invalid event payload discarded: %s", event.tradingId)
            return
        }

        // Idempotency
        if (persistencePort.findByTradingId(event.tradingId) != null) {
            log.infof("Trading %s already exists in DB, skipping persist", event.tradingId)
            return
        }

        val trading = FoodTrading(
            tradingId = event.tradingId,
            marketId = event.marketId.ifBlank { marketId },
            itemName = event.itemName,
            quantity = event.quantity,
            unitPrice = event.unitPrice,
            traderName = event.traderName,
            status = "CONFIRMED",
            createdAt = event.timestamp
        )
        trading.validateAndCalculate()

        val saved = persistencePort.save(trading)
        sseBroadcasterPort.broadcast(saved)
    }
}
