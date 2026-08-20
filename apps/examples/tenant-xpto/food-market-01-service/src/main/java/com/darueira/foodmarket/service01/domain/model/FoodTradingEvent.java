package com.darueira.foodmarket.service01.domain.model;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.Instant;

public class FoodTradingEvent implements Serializable {
    private String eventId;
    private String eventType;
    private String tradingId;
    private String marketId;
    private String itemName;
    private BigDecimal quantity;
    private BigDecimal unitPrice;
    private BigDecimal totalPrice;
    private String traderName;
    private String status;
    private Instant timestamp;

    public FoodTradingEvent() {
    }

    public FoodTradingEvent(String eventId, String eventType, String tradingId, String marketId, String itemName,
                            BigDecimal quantity, BigDecimal unitPrice, BigDecimal totalPrice, String traderName,
                            String status, Instant timestamp) {
        this.eventId = eventId;
        this.eventType = eventType;
        this.tradingId = tradingId;
        this.marketId = marketId;
        this.itemName = itemName;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
        this.totalPrice = totalPrice;
        this.traderName = traderName;
        this.status = status;
        this.timestamp = timestamp;
    }

    public String getEventId() { return eventId; }
    public void setEventId(String eventId) { this.eventId = eventId; }

    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }

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

    public Instant getTimestamp() { return timestamp; }
    public void setTimestamp(Instant timestamp) { this.timestamp = timestamp; }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String eventId;
        private String eventType;
        private String tradingId;
        private String marketId;
        private String itemName;
        private BigDecimal quantity;
        private BigDecimal unitPrice;
        private BigDecimal totalPrice;
        private String traderName;
        private String status;
        private Instant timestamp;

        public Builder eventId(String eventId) { this.eventId = eventId; return this; }
        public Builder eventType(String eventType) { this.eventType = eventType; return this; }
        public Builder tradingId(String tradingId) { this.tradingId = tradingId; return this; }
        public Builder marketId(String marketId) { this.marketId = marketId; return this; }
        public Builder itemName(String itemName) { this.itemName = itemName; return this; }
        public Builder quantity(BigDecimal quantity) { this.quantity = quantity; return this; }
        public Builder unitPrice(BigDecimal unitPrice) { this.unitPrice = unitPrice; return this; }
        public Builder totalPrice(BigDecimal totalPrice) { this.totalPrice = totalPrice; return this; }
        public Builder traderName(String traderName) { this.traderName = traderName; return this; }
        public Builder status(String status) { this.status = status; return this; }
        public Builder timestamp(Instant timestamp) { this.timestamp = timestamp; return this; }

        public FoodTradingEvent build() {
            return new FoodTradingEvent(eventId, eventType, tradingId, marketId, itemName, quantity, unitPrice, totalPrice, traderName, status, timestamp);
        }
    }
}
