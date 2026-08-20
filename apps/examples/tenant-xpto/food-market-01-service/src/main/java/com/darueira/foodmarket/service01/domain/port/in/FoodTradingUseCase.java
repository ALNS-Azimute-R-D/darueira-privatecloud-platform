package com.darueira.foodmarket.service01.domain.port.in;

import com.darueira.foodmarket.service01.domain.model.CreateFoodTradingCommand;
import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import com.darueira.foodmarket.service01.domain.model.FoodTradingEvent;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

public interface FoodTradingUseCase {
    FoodTrading createTrading(CreateFoodTradingCommand command);
    List<FoodTrading> listTradings();
    SseEmitter subscribeStream();
    void processIncomingEvent(FoodTradingEvent event);
}
