package com.darueira.foodmarket.service02.domain.port.`in`

import com.darueira.foodmarket.service02.domain.model.CreateFoodTradingCommand
import com.darueira.foodmarket.service02.domain.model.FoodTrading
import com.darueira.foodmarket.service02.domain.model.FoodTradingEvent
import io.smallrye.mutiny.Multi

interface FoodTradingUseCase {
    fun createTrading(command: CreateFoodTradingCommand): FoodTrading
    fun listTradings(): List<FoodTrading>
    fun subscribeStream(): Multi<FoodTrading>
    fun processIncomingEvent(event: FoodTradingEvent)
}
