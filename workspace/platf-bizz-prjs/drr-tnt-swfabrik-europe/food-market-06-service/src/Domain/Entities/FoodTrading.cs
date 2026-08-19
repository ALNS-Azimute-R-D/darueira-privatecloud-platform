namespace Darueira.FoodMarket.Service06.Domain.Entities;

public class FoodTrading
{
    public long? Id { get; set; }
    public string TradingId { get; set; } = string.Empty;
    public string MarketId { get; set; } = string.Empty;
    public string ItemName { get; set; } = string.Empty;
    public decimal Quantity { get; set; }
    public decimal UnitPrice { get; set; }
    public decimal TotalPrice { get; set; }
    public string TraderName { get; set; } = string.Empty;
    public string Status { get; set; } = "CONFIRMED";
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public void ValidateAndCalculate()
    {
        if (string.IsNullOrWhiteSpace(ItemName))
            throw new ArgumentException("itemName must not be blank");
        if (Quantity <= 0)
            throw new ArgumentException("quantity must be greater than zero");
        if (UnitPrice <= 0)
            throw new ArgumentException("unitPrice must be greater than zero");
        if (string.IsNullOrWhiteSpace(TraderName))
            throw new ArgumentException("traderName must not be blank");
        if (string.IsNullOrWhiteSpace(TradingId))
            TradingId = $"TRD-CS-{Guid.NewGuid().ToString("N")[..8].ToUpperInvariant()}";
        if (string.IsNullOrWhiteSpace(Status))
            Status = "CONFIRMED";

        TotalPrice = decimal.Round(Quantity * UnitPrice, 2);
    }
}
