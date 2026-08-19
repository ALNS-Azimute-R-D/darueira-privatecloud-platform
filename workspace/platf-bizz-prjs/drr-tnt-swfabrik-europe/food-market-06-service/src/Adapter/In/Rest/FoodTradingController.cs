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
        Response.Headers.Append("Cache-Control", "no-cache");
        Response.Headers.Append("Connection", "keep-alive");

        // Send initial event
        await Response.WriteAsync("event: INIT\ndata: {\"message\":\"Connected to Food Trading Live SSE Stream (Service 06 - .NET 8 / C#)\"}\n\n", ct);
        await Response.Body.FlushAsync(ct);

        await foreach (var trading in _useCase.SubscribeStreamAsync(ct))
        {
            var json = JsonSerializer.Serialize(FoodTradingResponse.FromDomain(trading));
            await Response.WriteAsync($"event: FOOD_TRADING_EVENT\ndata: {json}\n\n", ct);
            await Response.Body.FlushAsync(ct);
        }
    }
}
