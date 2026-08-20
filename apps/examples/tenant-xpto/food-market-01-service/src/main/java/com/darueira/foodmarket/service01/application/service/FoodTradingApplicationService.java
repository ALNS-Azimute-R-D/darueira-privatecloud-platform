package com.darueira.foodmarket.service01.application.service;

import com.darueira.foodmarket.service01.domain.model.CreateFoodTradingCommand;
import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import com.darueira.foodmarket.service01.domain.model.FoodTradingEvent;
import com.darueira.foodmarket.service01.domain.port.in.FoodTradingUseCase;
import com.darueira.foodmarket.service01.domain.port.out.FoodTradingEventPublisherPort;
import com.darueira.foodmarket.service01.domain.port.out.FoodTradingPersistencePort;
import com.darueira.foodmarket.service01.domain.port.out.FoodTradingSseBroadcasterPort;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class FoodTradingApplicationService implements FoodTradingUseCase {

    private static final Logger log = LoggerFactory.getLogger(FoodTradingApplicationService.class);

    private final FoodTradingPersistencePort persistencePort;
    private final FoodTradingEventPublisherPort publisherPort;
    private final FoodTradingSseBroadcasterPort sseBroadcasterPort;

    @Value("${app.market-id:MKT-EU-01-SPRING}")
    private String marketId;

    public FoodTradingApplicationService(FoodTradingPersistencePort persistencePort,
                                         FoodTradingEventPublisherPort publisherPort,
                                         FoodTradingSseBroadcasterPort sseBroadcasterPort) {
        this.persistencePort = persistencePort;
        this.publisherPort = publisherPort;
        this.sseBroadcasterPort = sseBroadcasterPort;
    }

    @Override
    @Transactional
    public FoodTrading createTrading(CreateFoodTradingCommand command) {
        log.info("[Spring Boot 01] Creating new food trading item: {} by {}", command.getItemName(), command.getTraderName());

        FoodTrading trading = FoodTrading.builder()
                .marketId(this.marketId)
                .itemName(command.getItemName())
                .quantity(command.getQuantity())
                .unitPrice(command.getUnitPrice())
                .traderName(command.getTraderName())
                .status("CONFIRMED")
                .createdAt(Instant.now())
                .build();

        trading.validateAndCalculate();

        // 1. Persist to PostgreSQL (F02)
        FoodTrading saved = persistencePort.save(trading);

        // 2. Publish Event to RabbitMQ Topic (F03)
        FoodTradingEvent event = FoodTradingEvent.builder()
                .eventId(UUID.randomUUID().toString())
                .eventType("FOOD_TRADING_CREATED")
                .tradingId(saved.getTradingId())
                .marketId(saved.getMarketId())
                .itemName(saved.getItemName())
                .quantity(saved.getQuantity())
                .unitPrice(saved.getUnitPrice())
                .totalPrice(saved.getTotalPrice())
                .traderName(saved.getTraderName())
                .status(saved.getStatus())
                .timestamp(Instant.now())
                .build();

        publisherPort.publishEvent(event);

        // 3. Broadcast to SSE (F01.3 / F04.2.3)
        sseBroadcasterPort.broadcast(saved);

        return saved;
    }

    @Override
    @Transactional(readOnly = true)
    public List<FoodTrading> listTradings() {
        return persistencePort.findAll();
    }

    @Override
    public SseEmitter subscribeStream() {
        return sseBroadcasterPort.registerClient();
    }

    @Override
    @Transactional
    public void processIncomingEvent(FoodTradingEvent event) {
        log.info("[Spring Boot 01] Consuming RabbitMQ message event: {}", event.getTradingId());

        // F04.2.1: Business validation
        if (event.getQuantity() == null || event.getUnitPrice() == null) {
            log.warn("Invalid event discarded: missing numerical fields");
            return;
        }

        // Check idempotency
        if (persistencePort.findByTradingId(event.getTradingId()).isPresent()) {
            log.info("Trading {} already exists in DB, skipping duplicate persist", event.getTradingId());
            return;
        }

        FoodTrading trading = FoodTrading.builder()
                .tradingId(event.getTradingId())
                .marketId(event.getMarketId() != null ? event.getMarketId() : this.marketId)
                .itemName(event.getItemName())
                .quantity(event.getQuantity())
                .unitPrice(event.getUnitPrice())
                .traderName(event.getTraderName())
                .status("CONFIRMED")
                .createdAt(event.getTimestamp() != null ? event.getTimestamp() : Instant.now())
                .build();

        trading.validateAndCalculate();

        // F04.2.2: Persist
        FoodTrading saved = persistencePort.save(trading);

        // F04.2.3: Push to SSE Stream
        sseBroadcasterPort.broadcast(saved);
    }
}
