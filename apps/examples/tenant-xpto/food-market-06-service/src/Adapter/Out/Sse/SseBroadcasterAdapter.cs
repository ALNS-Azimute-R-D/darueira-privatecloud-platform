using System.Threading.Channels;
using Darueira.FoodMarket.Service06.Domain.Entities;
using Darueira.FoodMarket.Service06.Port.Out;

namespace Darueira.FoodMarket.Service06.Adapter.Out.Sse;

public class SseBroadcasterAdapter : IFoodTradingSseBroadcasterPort
{
    private readonly ILogger<SseBroadcasterAdapter> _logger;
    private readonly List<Channel<FoodTrading>> _channels = new();
    private readonly object _lock = new();

    public SseBroadcasterAdapter(ILogger<SseBroadcasterAdapter> logger)
    {
        _logger = logger;
    }

    public async IAsyncEnumerable<FoodTrading> SubscribeAsync([System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken ct = default)
    {
        var channel = Channel.CreateBounded<FoodTrading>(new BoundedChannelOptions(100)
        {
            FullMode = BoundedChannelFullMode.DropOldest
        });

        lock (_lock)
        {
            _channels.Add(channel);
            _logger.LogInformation("[.NET 06] SSE client connected (Total: {Count})", _channels.Count);
        }

        try
        {
            while (!ct.IsCancellationRequested && await channel.Reader.WaitToReadAsync(ct))
            {
                while (channel.Reader.TryRead(out var item))
                {
                    yield return item;
                }
            }
        }
        finally
        {
            lock (_lock)
            {
                _channels.Remove(channel);
                _logger.LogInformation("[.NET 06] SSE client disconnected (Total: {Count})", _channels.Count);
            }
        }
    }

    public Task BroadcastAsync(FoodTrading trading, CancellationToken ct = default)
    {
        lock (_lock)
        {
            _logger.LogInformation("[.NET 06] Broadcasting food trading via SSE: {TradingId}", trading.TradingId);
            foreach (var ch in _channels)
            {
                ch.Writer.TryWrite(trading);
            }
        }
        return Task.CompletedTask;
    }
}
