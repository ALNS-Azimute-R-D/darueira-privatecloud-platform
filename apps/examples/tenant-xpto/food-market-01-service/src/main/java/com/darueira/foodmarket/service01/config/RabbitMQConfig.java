package com.darueira.foodmarket.service01.config;

import org.springframework.amqp.core.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    @Value("${app.rabbitmq.topic:marketplace.foodtrading.topic}")
    private String topicExchangeName;

    @Value("${app.rabbitmq.queue:marketplace.foodtrading.queue01}")
    private String queueName;

    @Bean
    public TopicExchange foodTradingTopicExchange() {
        return new TopicExchange(topicExchangeName, true, false);
    }

    @Bean
    public Queue foodTradingQueue() {
        return new Queue(queueName, true);
    }

    @Bean
    public Binding foodTradingBinding(Queue foodTradingQueue, TopicExchange foodTradingTopicExchange) {
        return BindingBuilder.bind(foodTradingQueue)
                .to(foodTradingTopicExchange)
                .with("#");
    }
}
