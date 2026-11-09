package com.darueira.foodmarket.service01.adapter.in.rest;

import com.darueira.foodmarket.service01.domain.model.FoodTrading;

import java.math.BigDecimal;
import java.time.Instant;

public class FoodTradingResponse {
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

    public FoodTradingResponse() {
    }

    public FoodTradingResponse(Long id, String tradingId, String marketId, String itemName, BigDecimal quantity,
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

    public static FoodTradingResponse fromDomain(FoodTrading trading) {
        return new FoodTradingResponse(
                trading.getId(),
                trading.getTradingId(),
                trading.getMarketId(),
                trading.getItemName(),
                trading.getQuantity(),
                trading.getUnitPrice(),
                trading.getTotalPrice(),
                trading.getTraderName(),
                trading.getStatus(),
                trading.getCreatedAt()
        );
    }

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
}
