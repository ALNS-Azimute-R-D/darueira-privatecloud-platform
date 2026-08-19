namespace Darueira.FoodMarket.Service06.Domain.Events;

public class FoodTradingEvent
{
    public string EventId { get; set; } = Guid.NewGuid().ToString();
    public string EventType { get; set; } = "FOOD_TRADING_CREATED";
    public string TradingId { get; set; } = string.Empty;
    public string MarketId { get; set; } = string.Empty;
    public string ItemName { get; set; } = string.Empty;
    public decimal Quantity { get; set; }
    public decimal UnitPrice { get; set; }
    public decimal TotalPrice { get; set; }
    public string TraderName { get; set; } = string.Empty;
    public string Status { get; set; } = "CONFIRMED";
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
}
