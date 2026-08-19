using System.Data;
using Darueira.FoodMarket.Service06.Domain.Entities;
using Darueira.FoodMarket.Service06.Port.Out;
using Npgsql;

namespace Darueira.FoodMarket.Service06.Adapter.Out.Persistence;

public class PostgresFoodTradingAdapter : IFoodTradingPersistencePort
{
    private readonly string _connectionString;

    public PostgresFoodTradingAdapter(IConfiguration config)
    {
        _connectionString = config["DATABASE_URL"] ??
            "Host=central-postgres.drr-corpshared-plat.svc.cluster.local;Port=5432;Database=drr_tnt_bizapps_db;Username=drr_admin;Password=change-me-in-openbao";
    }

    private NpgsqlConnection CreateConnection()
    {
        // Convert postgres:// URI to Npgsql connection string if needed
        if (_connectionString.StartsWith("postgres://") || _connectionString.StartsWith("postgresql://"))
        {
            var uri = new Uri(_connectionString);
            var userInfo = uri.UserInfo.Split(':');
            var user = userInfo[0];
            var pass = userInfo.Length > 1 ? userInfo[1] : "";
            var host = uri.Host;
            var port = uri.Port > 0 ? uri.Port : 5432;
            var db = uri.AbsolutePath.TrimStart('/');
            var connStr = $"Host={host};Port={port};Database={db};Username={user};Password={pass};SSL Mode=Disable";
            return new NpgsqlConnection(connStr);
        }
        return new NpgsqlConnection(_connectionString);
    }

    public async Task<FoodTrading> SaveAsync(FoodTrading trading, CancellationToken ct = default)
    {
        await using var conn = CreateConnection();
        await conn.OpenAsync(ct);

        const string sql = @"
            INSERT INTO schm06.tb_food_trading 
            (trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at)
            VALUES (@trading_id, @market_id, @item_name, @quantity, @unit_price, @total_price, @trader_name, @status, @created_at)
            RETURNING id;
        ";

        await using var cmd = new NpgsqlCommand(sql, conn);
        cmd.Parameters.AddWithValue("trading_id", trading.TradingId);
        cmd.Parameters.AddWithValue("market_id", trading.MarketId);
        cmd.Parameters.AddWithValue("item_name", trading.ItemName);
        cmd.Parameters.AddWithValue("quantity", trading.Quantity);
        cmd.Parameters.AddWithValue("unit_price", trading.UnitPrice);
        cmd.Parameters.AddWithValue("total_price", trading.TotalPrice);
        cmd.Parameters.AddWithValue("trader_name", trading.TraderName);
        cmd.Parameters.AddWithValue("status", trading.Status);
        cmd.Parameters.AddWithValue("created_at", trading.CreatedAt);

        var id = await cmd.ExecuteScalarAsync(ct);
        if (id != null && long.TryParse(id.ToString(), out var longId))
        {
            trading.Id = longId;
        }

        return trading;
    }

    public async Task<IReadOnlyList<FoodTrading>> FindAllAsync(CancellationToken ct = default)
    {
        await using var conn = CreateConnection();
        await conn.OpenAsync(ct);

        const string sql = @"
            SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at
            FROM schm06.tb_food_trading
            ORDER BY id DESC;
        ";

        await using var cmd = new NpgsqlCommand(sql, conn);
        await using var reader = await cmd.ExecuteReaderAsync(ct);

        var list = new List<FoodTrading>();
        while (await reader.ReadAsync(ct))
        {
            list.Add(new FoodTrading
            {
                Id = reader.GetInt64(0),
                TradingId = reader.GetString(1),
                MarketId = reader.GetString(2),
                ItemName = reader.GetString(3),
                Quantity = reader.GetDecimal(4),
                UnitPrice = reader.GetDecimal(5),
                TotalPrice = reader.GetDecimal(6),
                TraderName = reader.GetString(7),
                Status = reader.GetString(8),
                CreatedAt = reader.GetDateTime(9)
            });
        }

        return list;
    }

    public async Task<FoodTrading?> FindByTradingIdAsync(string tradingId, CancellationToken ct = default)
    {
        await using var conn = CreateConnection();
        await conn.OpenAsync(ct);

        const string sql = @"
            SELECT id, trading_id, market_id, item_name, quantity, unit_price, total_price, trader_name, status, created_at
            FROM schm06.tb_food_trading
            WHERE trading_id = @trading_id;
        ";

        await using var cmd = new NpgsqlCommand(sql, conn);
        cmd.Parameters.AddWithValue("trading_id", tradingId);

        await using var reader = await cmd.ExecuteReaderAsync(ct);
        if (await reader.ReadAsync(ct))
        {
            return new FoodTrading
            {
                Id = reader.GetInt64(0),
                TradingId = reader.GetString(1),
                MarketId = reader.GetString(2),
                ItemName = reader.GetString(3),
                Quantity = reader.GetDecimal(4),
                UnitPrice = reader.GetDecimal(5),
                TotalPrice = reader.GetDecimal(6),
                TraderName = reader.GetString(7),
                Status = reader.GetString(8),
                CreatedAt = reader.GetDateTime(9)
            };
        }

        return null;
    }
}
