using System.Text.Json;
using Darueira.FoodMarket.Service06.Adapter.In.Rest.Dtos;
using Darueira.FoodMarket.Service06.Domain.Commands;
using Darueira.FoodMarket.Service06.Port.In;
using Microsoft.AspNetCore.Mvc;

namespace Darueira.FoodMarket.Service06.Adapter.In.Rest;

[ApiController]
[Route("api/food-tradings")]
public class FoodTradingController : ControllerBase
{
    private readonly IFoodTradingUseCase _useCase;

    public FoodTradingController(IFoodTradingUseCase useCase)
    {
        _useCase = useCase;
    }

    [HttpPost]
    [ProducesResponseType(typeof(FoodTradingResponse), StatusCodes.Status201Created)]
    public async Task<IActionResult> CreateTrading([FromBody] CreateTradingRequest request, CancellationToken ct)
    {
        try
        {
            var command = new CreateFoodTradingCommand
            {
                ItemName = request.ItemName,
                Quantity = request.Quantity,
                UnitPrice = request.UnitPrice,
                TraderName = request.TraderName
            };

            var created = await _useCase.CreateTradingAsync(command, ct);
            return StatusCode(StatusCodes.Status201Created, FoodTradingResponse.FromDomain(created));
        }
        catch (ArgumentException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    [HttpGet]
    [ProducesResponseType(typeof(IReadOnlyList<FoodTradingResponse>), StatusCodes.Status200OK)]
    public async Task<IActionResult> ListTradings(CancellationToken ct)
    {
        var tradings = await _useCase.ListTradingsAsync(ct);
        var response = tradings.Select(FoodTradingResponse.FromDomain).ToList();
        return Ok(response);
    }

    [HttpGet("stream")]
    public async Task StreamTradings(CancellationToken ct)
    {
        Response.Headers.Append("Content-Type", "text/event-stream");
        Response.Headers.Append("Cache-Control", "no-cache, no-transform");
        Response.Headers.Append("Connection", "keep-alive");
        Response.Headers.Append("X-Accel-Buffering", "no");

        // Send initial event
        await Response.WriteAsync("event: INIT\ndata: {\"message\":\"Connected to Food Trading Live SSE Stream (Service 06 - .NET 8 / C#)\"}\n\n", ct);
        await Response.Body.FlushAsync(ct);

        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(10));
        var streamEnum = _useCase.SubscribeStreamAsync(ct).GetAsyncEnumerator(ct);

        try
        {
            while (!ct.IsCancellationRequested)
            {
                var nextTask = streamEnum.MoveNextAsync().AsTask();
                var timerTask = timer.WaitForNextTickAsync(ct).AsTask();

                var completed = await Task.WhenAny(nextTask, timerTask);
                if (completed == nextTask)
                {
                    if (await nextTask)
                    {
                        var trading = streamEnum.Current;
                        var json = JsonSerializer.Serialize(FoodTradingResponse.FromDomain(trading));
                        await Response.WriteAsync($"event: FOOD_TRADING_EVENT\ndata: {json}\n\n", ct);
                        await Response.Body.FlushAsync(ct);
                    }
                    else
                    {
                        break;
                    }
                }
                else
                {
                    await Response.WriteAsync(": ping\n\n", ct);
                    await Response.Body.FlushAsync(ct);
                }
            }
        }
        catch (OperationCanceledException)
        {
            // Client disconnected gracefully
        }
        finally
        {
            await streamEnum.DisposeAsync();
        }
    }
}
