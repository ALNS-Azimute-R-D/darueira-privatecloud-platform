using Darueira.FoodMarket.Service06.Domain.Commands;
using Darueira.FoodMarket.Service06.Domain.Entities;
using Darueira.FoodMarket.Service06.Domain.Events;
using Darueira.FoodMarket.Service06.Port.In;
using Darueira.FoodMarket.Service06.Port.Out;
using Microsoft.Extensions.Logging;

namespace Darueira.FoodMarket.Service06.Application;

public class FoodTradingApplicationService : IFoodTradingUseCase
{
    private readonly IFoodTradingPersistencePort _persistence;
    private readonly IFoodTradingEventPublisherPort _publisher;
    private readonly IFoodTradingSseBroadcasterPort _sseBroadcaster;
    private readonly ILogger<FoodTradingApplicationService> _logger;
    private readonly string _marketId;

    public FoodTradingApplicationService(
        IFoodTradingPersistencePort persistence,
        IFoodTradingEventPublisherPort publisher,
        IFoodTradingSseBroadcasterPort sseBroadcaster,
        ILogger<FoodTradingApplicationService> logger,
        IConfiguration config)
    {
        _persistence = persistence;
        _publisher = publisher;
        _sseBroadcaster = sseBroadcaster;
        _logger = logger;
        _marketId = config["APP_MARKET_ID"] ?? "MKT-EU-06-DOTNET";
    }

    public async Task<FoodTrading> CreateTradingAsync(CreateFoodTradingCommand command, CancellationToken ct = default)
    {
        _logger.LogInformation("[.NET 06] Creating food trading: {ItemName} by {TraderName}", command.ItemName, command.TraderName);

        var trading = new FoodTrading
        {
            MarketId = _marketId,
            ItemName = command.ItemName,
            Quantity = command.Quantity,
            UnitPrice = command.UnitPrice,
            TraderName = command.TraderName,
            Status = "CONFIRMED",
            CreatedAt = DateTime.UtcNow
        };

        trading.ValidateAndCalculate();

        // 1. Persist (F02)
        var saved = await _persistence.SaveAsync(trading, ct);

        // 2. Publish to RabbitMQ Topic (F03)
        var tradingEvent = new FoodTradingEvent
        {
            TradingId = saved.TradingId,
            MarketId = saved.MarketId,
            ItemName = saved.ItemName,
            Quantity = saved.Quantity,
            UnitPrice = saved.UnitPrice,
            TotalPrice = saved.TotalPrice,
            TraderName = saved.TraderName,
            Status = saved.Status,
            Timestamp = saved.CreatedAt
        };

        await _publisher.PublishEventAsync(tradingEvent, ct);

        // 3. Broadcast to SSE (F01.3 / F04.2.3)
        await _sseBroadcaster.BroadcastAsync(saved, ct);

        return saved;
    }

    public async Task<IReadOnlyList<FoodTrading>> ListTradingsAsync(CancellationToken ct = default)
    {
        return await _persistence.FindAllAsync(ct);
    }

    public IAsyncEnumerable<FoodTrading> SubscribeStreamAsync(CancellationToken ct = default)
    {
        return _sseBroadcaster.SubscribeAsync(ct);
    }

    public async Task ProcessIncomingEventAsync(FoodTradingEvent tradingEvent, CancellationToken ct = default)
    {
        _logger.LogInformation("[.NET 06] Consuming RabbitMQ message event: {TradingId}", tradingEvent.TradingId);

        if (tradingEvent.Quantity <= 0 || tradingEvent.UnitPrice <= 0)
        {
            _logger.LogWarning("Discarding invalid event: {TradingId}", tradingEvent.TradingId);
            return;
        }

        var existing = await _persistence.FindByTradingIdAsync(tradingEvent.TradingId, ct);
        if (existing != null)
        {
            _logger.LogInformation("Trading {TradingId} already exists in DB, skipping duplicate persist", tradingEvent.TradingId);
            return;
        }

        var trading = new FoodTrading
        {
            TradingId = tradingEvent.TradingId,
            MarketId = string.IsNullOrWhiteSpace(tradingEvent.MarketId) ? _marketId : tradingEvent.MarketId,
            ItemName = tradingEvent.ItemName,
            Quantity = tradingEvent.Quantity,
            UnitPrice = tradingEvent.UnitPrice,
            TraderName = tradingEvent.TraderName,
            Status = "CONFIRMED",
            CreatedAt = tradingEvent.Timestamp
        };

        trading.ValidateAndCalculate();

        var saved = await _persistence.SaveAsync(trading, ct);
        await _sseBroadcaster.BroadcastAsync(saved, ct);
    }
}
