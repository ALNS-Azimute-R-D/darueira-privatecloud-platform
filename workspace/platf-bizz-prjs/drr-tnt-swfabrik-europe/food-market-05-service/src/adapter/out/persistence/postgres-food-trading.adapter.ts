import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { Pool } from 'pg';
import { FoodTrading } from '../../../domain/food-trading.entity';
import { FoodTradingPersistencePort } from '../../../port/out/persistence.port';

@Injectable()
export class PostgresFoodTradingAdapter implements FoodTradingPersistencePort, OnModuleInit, OnModuleDestroy {
  private pool: Pool;

  onModuleInit() {
    const connectionString =
      process.env.DATABASE_URL ||
      'postgres://drr_admin:change-me-in-openbao@central-postgres.drr-corpshared-plat.svc.cluster.local:5432/drr_tnt_bizapps_db?sslmode=disable';

    this.pool = new Pool({
      connectionString: connectionString.replace('?sslmode=disable', ''),
      max: 10,
    });
  }

  async onModuleDestroy() {
    if (this.pool) {
      await this.pool.end();
    }
  }

  async save(trading: FoodTrading): Promise<FoodTrading> {
    const sql = `
      INSERT INTO schm05.tb_food_trading 
      (trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
      RETURNING id
    `;

    const res = await this.pool.query(sql, [
      trading.tradingId,
      trading.marketId,
      trading.itemName,
      trading.quantity,
      trading.unitPrice,
      trading.totalPrice,
      trading.traderName,
      trading.status,
      trading.createdAt,
    ]);

    trading.id = res.rows[0].id;
    return trading;
  }

  async findAll(): Promise<FoodTrading[]> {
    const sql = `
      SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at
      FROM schm05.tb_food_trading
      ORDER BY id DESC
    `;

    const res = await this.pool.query(sql);
    return res.rows.map(
      (row) =>
        new FoodTrading({
          id: row.id,
          tradingId: row.trading_id,
          marketId: row.market_id,
          itemName: row.item_name,
          quantity: Number(row.quantity),
          unitPrice: Number(row.unit_price),
          totalPrice: Number(row.total_price),
          traderName: row.trader_name,
          status: row.status,
          createdAt: new Date(row.created_at),
        }),
    );
  }

  async findByTradingId(tradingId: string): Promise<FoodTrading | null> {
    const sql = `
      SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at
      FROM schm05.tb_food_trading
      WHERE trading_id = $1
    `;

    const res = await this.pool.query(sql, [tradingId]);
    if (res.rows.length === 0) {
      return null;
    }
    const row = res.rows[0];
    return new FoodTrading({
      id: row.id,
      tradingId: row.trading_id,
      marketId: row.market_id,
      itemName: row.item_name,
      quantity: Number(row.quantity),
      unitPrice: Number(row.unit_price),
      totalPrice: Number(row.total_price),
      traderName: row.trader_name,
      status: row.status,
      createdAt: new Date(row.created_at),
    });
  }
}
