package com.darueira.foodmarket.service02.domain.port.out

import com.darueira.foodmarket.service02.domain.model.FoodTrading
import com.darueira.foodmarket.service02.domain.model.FoodTradingEvent
import io.smallrye.mutiny.Multi

interface FoodTradingPersistencePort {
    fun save(trading: FoodTrading): FoodTrading
    fun findAll(): List<FoodTrading>
    fun findByTradingId(tradingId: String): FoodTrading?
}

interface FoodTradingEventPublisherPort {
    fun publishEvent(event: FoodTradingEvent)
}

interface FoodTradingSseBroadcasterPort {
    fun stream(): Multi<FoodTrading>
    fun broadcast(trading: FoodTrading)
}
