package com.darueira.foodmarket.service01.domain.port.out;

import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

public interface FoodTradingSseBroadcasterPort {
    SseEmitter registerClient();
    void broadcast(FoodTrading trading);
}
