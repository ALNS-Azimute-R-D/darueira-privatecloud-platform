using Darueira.FoodMarket.Service06.Domain.Entities;
using Darueira.FoodMarket.Service06.Domain.Events;

namespace Darueira.FoodMarket.Service06.Port.Out;

public interface IFoodTradingPersistencePort
{
    Task<FoodTrading> SaveAsync(FoodTrading trading, CancellationToken ct = default);
    Task<IReadOnlyList<FoodTrading>> FindAllAsync(CancellationToken ct = default);
    Task<FoodTrading?> FindByTradingIdAsync(string tradingId, CancellationToken ct = default);
}

public interface IFoodTradingEventPublisherPort
{
    Task PublishEventAsync(FoodTradingEvent tradingEvent, CancellationToken ct = default);
}

public interface IFoodTradingSseBroadcasterPort
{
    IAsyncEnumerable<FoodTrading> SubscribeAsync(CancellationToken ct = default);
    Task BroadcastAsync(FoodTrading trading, CancellationToken ct = default);
}
