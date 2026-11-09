package com.darueira.foodmarket.service01;

import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.*;

class FoodTradingDomainTest {

    @Test
    @DisplayName("Should validate and compute total price for food trading")
    void testFoodTradingValidationAndCalculation() {
        FoodTrading trading = FoodTrading.builder()
                .itemName("Valencia Oranges")
                .quantity(new BigDecimal("100.00"))
                .unitPrice(new BigDecimal("2.50"))
                .traderName("Iberia Fresh SL")
                .build();

        trading.validateAndCalculate();

        assertNotNull(trading.getTradingId());
        assertTrue(trading.getTradingId().startsWith("TRD-JAVA-"));
        assertEquals(new BigDecimal("250.0000"), trading.getTotalPrice());
        assertEquals("CONFIRMED", trading.getStatus());
        assertNotNull(trading.getCreatedAt());
    }

    @Test
    @DisplayName("Should reject invalid quantity")
    void testInvalidQuantity() {
        FoodTrading trading = FoodTrading.builder()
                .itemName("Valencia Oranges")
                .quantity(new BigDecimal("-5.00"))
                .unitPrice(new BigDecimal("2.50"))
                .traderName("Iberia Fresh SL")
                .build();

        assertThrows(IllegalArgumentException.class, trading::validateAndCalculate);
    }
}
