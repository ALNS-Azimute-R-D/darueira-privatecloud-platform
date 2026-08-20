package com.darueira.foodmarket.service01.domain.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

public class FoodTrading {
    private Long id;
    private String tradingId;
    private String marketId;
    private String itemName;
    private BigDecimal quantity;
    private BigDecimal unitPrice;
    private BigDecimal totalPrice;
    private String traderName;
    private String status;
    private Instant createdAt;

    public FoodTrading() {
    }

    public FoodTrading(Long id, String tradingId, String marketId, String itemName, BigDecimal quantity,
                       BigDecimal unitPrice, BigDecimal totalPrice, String traderName, String status, Instant createdAt) {
        this.id = id;
        this.tradingId = tradingId;
        this.marketId = marketId;
        this.itemName = itemName;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
        this.totalPrice = totalPrice;
        this.traderName = traderName;
        this.status = status;
        this.createdAt = createdAt;
    }

    public void validateAndCalculate() {
        if (itemName == null || itemName.trim().isEmpty()) {
            throw new IllegalArgumentException("Item name must not be blank");
        }
        if (quantity == null || quantity.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Quantity must be greater than zero");
        }
        if (unitPrice == null || unitPrice.compareTo(BigDecimal.ZERO) <= 0) {
            throw new IllegalArgumentException("Unit price must be greater than zero");
        }
        if (traderName == null || traderName.trim().isEmpty()) {
            throw new IllegalArgumentException("Trader name must not be blank");
        }
        if (tradingId == null || tradingId.trim().isEmpty()) {
            this.tradingId = "TRD-JAVA-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
        }
        if (status == null || status.trim().isEmpty()) {
            this.status = "CONFIRMED";
        }
        if (createdAt == null) {
            this.createdAt = Instant.now();
        }
        this.totalPrice = this.quantity.multiply(this.unitPrice);
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getTradingId() { return tradingId; }
    public void setTradingId(String tradingId) { this.tradingId = tradingId; }

    public String getMarketId() { return marketId; }
    public void setMarketId(String marketId) { this.marketId = marketId; }

    public String getItemName() { return itemName; }
    public void setItemName(String itemName) { this.itemName = itemName; }

    public BigDecimal getQuantity() { return quantity; }
    public void setQuantity(BigDecimal quantity) { this.quantity = quantity; }

    public BigDecimal getUnitPrice() { return unitPrice; }
    public void setUnitPrice(BigDecimal unitPrice) { this.unitPrice = unitPrice; }

    public BigDecimal getTotalPrice() { return totalPrice; }
    public void setTotalPrice(BigDecimal totalPrice) { this.totalPrice = totalPrice; }

    public String getTraderName() { return traderName; }
    public void setTraderName(String traderName) { this.traderName = traderName; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private Long id;
        private String tradingId;
        private String marketId;
        private String itemName;
        private BigDecimal quantity;
        private BigDecimal unitPrice;
        private BigDecimal totalPrice;
        private String traderName;
        private String status;
        private Instant createdAt;

        public Builder id(Long id) { this.id = id; return this; }
        public Builder tradingId(String tradingId) { this.tradingId = tradingId; return this; }
        public Builder marketId(String marketId) { this.marketId = marketId; return this; }
        public Builder itemName(String itemName) { this.itemName = itemName; return this; }
        public Builder quantity(BigDecimal quantity) { this.quantity = quantity; return this; }
        public Builder unitPrice(BigDecimal unitPrice) { this.unitPrice = unitPrice; return this; }
        public Builder totalPrice(BigDecimal totalPrice) { this.totalPrice = totalPrice; return this; }
        public Builder traderName(String traderName) { this.traderName = traderName; return this; }
        public Builder status(String status) { this.status = status; return this; }
        public Builder createdAt(Instant createdAt) { this.createdAt = createdAt; return this; }

        public FoodTrading build() {
            return new FoodTrading(id, tradingId, marketId, itemName, quantity, unitPrice, totalPrice, traderName, status, createdAt);
        }
    }
}
