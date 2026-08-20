using Darueira.FoodMarket.Service06.Domain.Commands;
using Darueira.FoodMarket.Service06.Domain.Entities;
using Darueira.FoodMarket.Service06.Domain.Events;

namespace Darueira.FoodMarket.Service06.Port.In;

public interface IFoodTradingUseCase
{
    Task<FoodTrading> CreateTradingAsync(CreateFoodTradingCommand command, CancellationToken ct = default);
    Task<IReadOnlyList<FoodTrading>> ListTradingsAsync(CancellationToken ct = default);
    IAsyncEnumerable<FoodTrading> SubscribeStreamAsync(CancellationToken ct = default);
    Task ProcessIncomingEventAsync(FoodTradingEvent tradingEvent, CancellationToken ct = default);
}
