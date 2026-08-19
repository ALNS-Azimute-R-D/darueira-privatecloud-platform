package com.darueira.foodmarket.service01.adapter.out.persistence;

import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import jakarta.persistence.*;

import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(name = "tb_food_trading", schema = "schm01")
public class FoodTradingJpaEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "trading_id", unique = true, nullable = false, length = 64)
    private String tradingId;

    @Column(name = "market_id", nullable = false, length = 64)
    private String marketId;

    @Column(name = "item_name", nullable = false, length = 128)
    private String itemName;

    @Column(name = "quantity", nullable = false, precision = 12, scale = 2)
    private BigDecimal quantity;

    @Column(name = "unit_price", nullable = false, precision = 12, scale = 2)
    private BigDecimal unitPrice;

    @Column(name = "total_price", nullable = false, precision = 12, scale = 2)
    private BigDecimal totalPrice;

    @Column(name = "trader_name", nullable = false, length = 128)
    private String traderName;

    @Column(name = "status", nullable = false, length = 32)
    private String status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public FoodTradingJpaEntity() {
    }

    public FoodTradingJpaEntity(Long id, String tradingId, String marketId, String itemName, BigDecimal quantity,
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

    public FoodTrading toDomain() {
        return new FoodTrading(
                this.id,
                this.tradingId,
                this.marketId,
                this.itemName,
                this.quantity,
                this.unitPrice,
                this.totalPrice,
                this.traderName,
                this.status,
                this.createdAt
        );
    }

    public static FoodTradingJpaEntity fromDomain(FoodTrading domain) {
        return new FoodTradingJpaEntity(
                domain.getId(),
                domain.getTradingId(),
                domain.getMarketId(),
                domain.getItemName(),
                domain.getQuantity(),
                domain.getUnitPrice(),
                domain.getTotalPrice(),
                domain.getTraderName(),
                domain.getStatus(),
                domain.getCreatedAt() != null ? domain.getCreatedAt() : Instant.now()
        );
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
}
