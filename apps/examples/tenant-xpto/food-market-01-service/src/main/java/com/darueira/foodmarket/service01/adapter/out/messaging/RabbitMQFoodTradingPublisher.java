package com.darueira.foodmarket.service01.adapter.out.messaging;

import com.darueira.foodmarket.service01.domain.model.FoodTradingEvent;
import com.darueira.foodmarket.service01.domain.port.out.FoodTradingEventPublisherPort;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class RabbitMQFoodTradingPublisher implements FoodTradingEventPublisherPort {

    private static final Logger log = LoggerFactory.getLogger(RabbitMQFoodTradingPublisher.class);

    private final RabbitTemplate rabbitTemplate;
    private final ObjectMapper objectMapper;

    @Value("${app.rabbitmq.topic:marketplace.foodtrading.topic}")
    private String exchangeName;

    public RabbitMQFoodTradingPublisher(RabbitTemplate rabbitTemplate, ObjectMapper objectMapper) {
        this.rabbitTemplate = rabbitTemplate;
        this.objectMapper = objectMapper;
    }

    @Override
    public void publishEvent(FoodTradingEvent event) {
        try {
            String routingKey = "foodtrading.created." + (event.getMarketId() != null ? event.getMarketId().toLowerCase() : "default");
            String jsonPayload = objectMapper.writeValueAsString(event);
            log.info("[Spring Boot 01] Publishing event to exchange '{}' with key '{}': {}", exchangeName, routingKey, event.getTradingId());
            rabbitTemplate.convertAndSend(exchangeName, routingKey, jsonPayload);
        } catch (Exception e) {
            log.error("[Spring Boot 01] Failed to publish message to RabbitMQ: {}", e.getMessage(), e);
        }
    }
}
