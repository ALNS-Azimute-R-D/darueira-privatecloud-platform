package com.darueira.foodmarket.service02.domain.model

import java.math.BigDecimal
import java.time.Instant
import java.util.UUID

data class FoodTrading(
    var id: Long? = null,
    var tradingId: String? = null,
    var marketId: String,
    var itemName: String,
    var quantity: BigDecimal,
    var unitPrice: BigDecimal,
    var totalPrice: BigDecimal? = null,
    var traderName: String,
    var status: String = "CONFIRMED",
    var createdAt: Instant = Instant.now()
) {
    fun validateAndCalculate() {
        require(itemName.isNotBlank()) { "Item name must not be blank" }
        require(quantity > BigDecimal.ZERO) { "Quantity must be greater than zero" }
        require(unitPrice > BigDecimal.ZERO) { "Unit price must be greater than zero" }
        require(traderName.isNotBlank()) { "Trader name must not be blank" }

        if (tradingId.isNullOrBlank()) {
            tradingId = "TRD-KT-" + UUID.randomUUID().toString().substring(0, 8).uppercase()
        }
        totalPrice = quantity.multiply(unitPrice)
    }
}

data class FoodTradingEvent(
    val eventId: String = UUID.randomUUID().toString(),
    val eventType: String = "FOOD_TRADING_CREATED",
    val tradingId: String,
    val marketId: String,
    val itemName: String,
    val quantity: BigDecimal,
    val unitPrice: BigDecimal,
    val totalPrice: BigDecimal,
    val traderName: String,
    val status: String = "CONFIRMED",
    val timestamp: Instant = Instant.now()
)

data class CreateFoodTradingCommand(
    val itemName: String,
    val quantity: BigDecimal,
    val unitPrice: BigDecimal,
    val traderName: String
)
