namespace Darueira.FoodMarket.Service06.Domain.Commands;

public class CreateFoodTradingCommand
{
    public string ItemName { get; set; } = string.Empty;
    public decimal Quantity { get; set; }
    public decimal UnitPrice { get; set; }
    public string TraderName { get; set; } = string.Empty;
}
