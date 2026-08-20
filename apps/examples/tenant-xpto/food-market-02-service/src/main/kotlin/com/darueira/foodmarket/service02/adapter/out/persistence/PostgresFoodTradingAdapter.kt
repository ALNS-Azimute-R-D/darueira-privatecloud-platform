package com.darueira.foodmarket.service02.adapter.out.persistence

import com.darueira.foodmarket.service02.domain.model.FoodTrading
import com.darueira.foodmarket.service02.domain.port.out.FoodTradingPersistencePort
import io.agroal.api.AgroalDataSource
import jakarta.enterprise.context.ApplicationScoped
import java.sql.ResultSet
import java.sql.Timestamp
import java.time.Instant

@ApplicationScoped
class PostgresFoodTradingAdapter(
    private val dataSource: AgroalDataSource
) : FoodTradingPersistencePort {

    override fun save(trading: FoodTrading): FoodTrading {
        val sql = """
            INSERT INTO schm02.tb_food_trading 
            (trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """.trimIndent()

        dataSource.connection.use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, trading.tradingId)
                stmt.setString(2, trading.marketId)
                stmt.setString(3, trading.itemName)
                stmt.setBigDecimal(4, trading.quantity)
                stmt.setBigDecimal(5, trading.unitPrice)
                stmt.setBigDecimal(6, trading.totalPrice)
                stmt.setString(7, trading.traderName)
                stmt.setString(8, trading.status)
                stmt.setTimestamp(9, Timestamp.from(trading.createdAt))

                stmt.executeQuery().use { rs ->
                    if (rs.next()) {
                        trading.id = rs.getLong("id")
                    }
                }
            }
        }
        return trading
    }

    override fun findAll(): List<FoodTrading> {
        val sql = "SELECT * FROM schm02.tb_food_trading ORDER BY id DESC"
        val list = mutableListOf<FoodTrading>()

        dataSource.connection.use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.executeQuery().use { rs ->
                    while (rs.next()) {
                        list.add(mapRow(rs))
                    }
                }
            }
        }
        return list
    }

    override fun findByTradingId(tradingId: String): FoodTrading? {
        val sql = "SELECT * FROM schm02.tb_food_trading WHERE trading_id = ?"
        dataSource.connection.use { conn ->
            conn.prepareStatement(sql).use { stmt ->
                stmt.setString(1, tradingId)
                stmt.executeQuery().use { rs ->
                    if (rs.next()) {
                        return mapRow(rs)
                    }
                }
            }
        }
        return null
    }

    private fun mapRow(rs: ResultSet): FoodTrading {
        return FoodTrading(
            id = rs.getLong("id"),
            tradingId = rs.getString("trading_id"),
            marketId = rs.getString("market_id"),
            itemName = rs.getString("item_name"),
            quantity = rs.getBigDecimal("quantity"),
            unitPrice = rs.getBigDecimal("unit_price"),
            totalPrice = rs.getBigDecimal("total_price"),
            traderName = rs.getString("trader_name"),
            status = rs.getString("status"),
            createdAt = rs.getTimestamp("created_at")?.toInstant() ?: Instant.now()
        )
    }
}
