package persistence

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/darueira/foodmarket/service03/internal/domain"
	_ "github.com/lib/pq"
)

type PostgresAdapter struct {
	db *sql.DB
}

func NewPostgresAdapter(db *sql.DB) *PostgresAdapter {
	return &PostgresAdapter{db: db}
}

func (a *PostgresAdapter) Save(ctx context.Context, trading *domain.FoodTrading) (*domain.FoodTrading, error) {
	query := `
		INSERT INTO schm03.tb_food_trading 
		(trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		RETURNING id
	`

	var id int64
	err := a.db.QueryRowContext(
		ctx,
		query,
		trading.TradingID,
		trading.MarketID,
		trading.ItemName,
		trading.Quantity,
		trading.UnitPrice,
		trading.TotalPrice,
		trading.TraderName,
		trading.Status,
		trading.CreatedAt,
	).Scan(&id)

	if err != nil {
		return nil, fmt.Errorf("failed to insert trading in schm03: %w", err)
	}

	trading.ID = id
	return trading, nil
}

func (a *PostgresAdapter) FindAll(ctx context.Context) ([]domain.FoodTrading, error) {
	query := `SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at 
	          FROM schm03.tb_food_trading ORDER BY id DESC`

	rows, err := a.db.QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var list []domain.FoodTrading
	for rows.Next() {
		var t domain.FoodTrading
		if err := rows.Scan(&t.ID, &t.TradingID, &t.MarketID, &t.ItemName, &t.Quantity, &t.UnitPrice, &t.TotalPrice, &t.TraderName, &t.Status, &t.CreatedAt); err != nil {
			return nil, err
		}
		list = append(list, t)
	}
	return list, nil
}

func (a *PostgresAdapter) FindByTradingID(ctx context.Context, tradingID string) (*domain.FoodTrading, error) {
	query := `SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at 
	          FROM schm03.tb_food_trading WHERE trading_id = $1`

	var t domain.FoodTrading
	err := a.db.QueryRowContext(ctx, query, tradingID).Scan(
		&t.ID, &t.TradingID, &t.MarketID, &t.ItemName, &t.Quantity, &t.UnitPrice, &t.TotalPrice, &t.TraderName, &t.Status, &t.CreatedAt,
	)
	if err != nil {
		if errorsIs(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &t, nil
}

func errorsIs(err, target error) bool {
	return err == target
}
