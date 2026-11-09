package com.darueira.foodmarket.service01.domain.port.out;

import com.darueira.foodmarket.service01.domain.model.FoodTradingEvent;

public interface FoodTradingEventPublisherPort {
    void publishEvent(FoodTradingEvent event);
}
