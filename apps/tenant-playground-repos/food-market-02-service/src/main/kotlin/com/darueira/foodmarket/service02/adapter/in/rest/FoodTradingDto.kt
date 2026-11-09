package com.darueira.foodmarket.service02.adapter.`in`.rest

import com.darueira.foodmarket.service02.domain.model.FoodTrading
import com.fasterxml.jackson.annotation.JsonProperty
import java.math.BigDecimal
import java.time.Instant

data class CreateTradingRequest(
    @JsonProperty("itemName")
    var itemName: String = "",

    @JsonProperty("quantity")
    var quantity: BigDecimal = BigDecimal.ZERO,

    @JsonProperty("unitPrice")
    var unitPrice: BigDecimal = BigDecimal.ZERO,

    @JsonProperty("traderName")
    var traderName: String = ""
)

data class FoodTradingResponse(
    var id: Long? = null,
    var tradingId: String? = null,
    var marketId: String = "",
    var itemName: String = "",
    var quantity: BigDecimal = BigDecimal.ZERO,
    var unitPrice: BigDecimal = BigDecimal.ZERO,
    var totalPrice: BigDecimal? = null,
    var traderName: String = "",
    var status: String = "CONFIRMED",
    var createdAt: Instant = Instant.now()
) {
    companion object {
        fun fromDomain(trading: FoodTrading): FoodTradingResponse {
            return FoodTradingResponse(
                id = trading.id,
                tradingId = trading.tradingId,
                marketId = trading.marketId,
                itemName = trading.itemName,
                quantity = trading.quantity,
                unitPrice = trading.unitPrice,
                totalPrice = trading.totalPrice,
                traderName = trading.traderName,
                status = trading.status,
                createdAt = trading.createdAt
            )
        }
    }
}
