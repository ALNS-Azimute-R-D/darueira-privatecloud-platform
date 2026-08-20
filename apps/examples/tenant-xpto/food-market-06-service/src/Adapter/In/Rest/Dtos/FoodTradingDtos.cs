using System.ComponentModel.DataAnnotations;
using Darueira.FoodMarket.Service06.Domain.Entities;

namespace Darueira.FoodMarket.Service06.Adapter.In.Rest.Dtos;

public class CreateTradingRequest
{
    [Required]
    public string ItemName { get; set; } = string.Empty;

    [Range(0.01, double.MaxValue, ErrorMessage = "quantity must be greater than zero")]
    public decimal Quantity { get; set; }

    [Range(0.01, double.MaxValue, ErrorMessage = "unitPrice must be greater than zero")]
    public decimal UnitPrice { get; set; }

    [Required]
    public string TraderName { get; set; } = string.Empty;
}

public class FoodTradingResponse
{
    public long? Id { get; set; }
    public string TradingId { get; set; } = string.Empty;
    public string MarketId { get; set; } = string.Empty;
    public string ItemName { get; set; } = string.Empty;
    public decimal Quantity { get; set; }
    public decimal UnitPrice { get; set; }
    public decimal TotalPrice { get; set; }
    public string TraderName { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; }

    public static FoodTradingResponse FromDomain(FoodTrading t) => new()
    {
        Id = t.Id,
        TradingId = t.TradingId,
        MarketId = t.MarketId,
        ItemName = t.ItemName,
        Quantity = t.Quantity,
        UnitPrice = t.UnitPrice,
        TotalPrice = t.TotalPrice,
        TraderName = t.TraderName,
        Status = t.Status,
        CreatedAt = t.CreatedAt
    };
}
