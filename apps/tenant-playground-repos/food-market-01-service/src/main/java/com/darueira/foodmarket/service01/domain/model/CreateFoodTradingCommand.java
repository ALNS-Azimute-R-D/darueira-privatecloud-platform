package com.darueira.foodmarket.service01.domain.model;

import java.math.BigDecimal;

public class CreateFoodTradingCommand {
    private String itemName;
    private BigDecimal quantity;
    private BigDecimal unitPrice;
    private String traderName;

    public CreateFoodTradingCommand() {
    }

    public CreateFoodTradingCommand(String itemName, BigDecimal quantity, BigDecimal unitPrice, String traderName) {
        this.itemName = itemName;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
        this.traderName = traderName;
    }

    public String getItemName() { return itemName; }
    public void setItemName(String itemName) { this.itemName = itemName; }

    public BigDecimal getQuantity() { return quantity; }
    public void setQuantity(BigDecimal quantity) { this.quantity = quantity; }

    public BigDecimal getUnitPrice() { return unitPrice; }
    public void setUnitPrice(BigDecimal unitPrice) { this.unitPrice = unitPrice; }

    public String getTraderName() { return traderName; }
    public void setTraderName(String traderName) { this.traderName = traderName; }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String itemName;
        private BigDecimal quantity;
        private BigDecimal unitPrice;
        private String traderName;

        public Builder itemName(String itemName) { this.itemName = itemName; return this; }
        public Builder quantity(BigDecimal quantity) { this.quantity = quantity; return this; }
        public Builder unitPrice(BigDecimal unitPrice) { this.unitPrice = unitPrice; return this; }
        public Builder traderName(String traderName) { this.traderName = traderName; return this; }

        public CreateFoodTradingCommand build() {
            return new CreateFoodTradingCommand(itemName, quantity, unitPrice, traderName);
        }
    }
}
