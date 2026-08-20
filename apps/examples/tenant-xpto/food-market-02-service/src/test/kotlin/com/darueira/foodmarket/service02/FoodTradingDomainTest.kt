package com.darueira.foodmarket.service02

import com.darueira.foodmarket.service02.domain.model.FoodTrading
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test
import java.math.BigDecimal

class FoodTradingDomainTest {

    @Test
    @DisplayName("Should validate and compute total price in Kotlin")
    fun testKotlinFoodTradingValidation() {
        val trading = FoodTrading(
            marketId = "MKT-EU-02-QUARKUS",
            itemName = "Greek Kalamata Olives",
            quantity = BigDecimal("200.00"),
            unitPrice = BigDecimal("8.50"),
            traderName = "Hellenic Goods SA"
        )
        trading.validateAndCalculate()

        assertNotNull(trading.tradingId)
        assertTrue(trading.tradingId!!.startsWith("TRD-KT-"))
        assertEquals(BigDecimal("1700.0000"), trading.totalPrice)
        assertEquals("CONFIRMED", trading.status)
    }

    @Test
    @DisplayName("Should reject invalid blank name in Kotlin")
    fun testInvalidBlankName() {
        val trading = FoodTrading(
            marketId = "MKT-EU-02-QUARKUS",
            itemName = "",
            quantity = BigDecimal("200.00"),
            unitPrice = BigDecimal("8.50"),
            traderName = "Hellenic Goods SA"
        )
        assertThrows(IllegalArgumentException::class.java) {
            trading.validateAndCalculate()
        }
    }
}
