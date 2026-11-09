package com.darueira.foodmarket.service01.adapter.in.messaging;

import com.darueira.foodmarket.service01.domain.model.FoodTradingEvent;
import com.darueira.foodmarket.service01.domain.port.in.FoodTradingUseCase;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

@Component
public class RabbitMQFoodTradingConsumer {

    private static final Logger log = LoggerFactory.getLogger(RabbitMQFoodTradingConsumer.class);

    private final FoodTradingUseCase useCase;
    private final ObjectMapper objectMapper;

    public RabbitMQFoodTradingConsumer(FoodTradingUseCase useCase, ObjectMapper objectMapper) {
        this.useCase = useCase;
        this.objectMapper = objectMapper;
    }

    @RabbitListener(queues = "${app.rabbitmq.queue:marketplace.foodtrading.queue01}")
    public void handleFoodTradingMessage(String payload) {
        log.info("[Spring Boot 01] Received RabbitMQ raw payload from queue01: {}", payload);
        try {
            FoodTradingEvent event = objectMapper.readValue(payload, FoodTradingEvent.class);
            useCase.processIncomingEvent(event);
        } catch (Exception e) {
            log.error("[Spring Boot 01] Failed to process message from RabbitMQ queue: {}", e.getMessage(), e);
        }
    }
}
