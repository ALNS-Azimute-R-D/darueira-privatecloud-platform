using Darueira.FoodMarket.Service06.Adapter.In.Messaging;
using Darueira.FoodMarket.Service06.Adapter.Out.Messaging;
using Darueira.FoodMarket.Service06.Adapter.Out.Persistence;
using Darueira.FoodMarket.Service06.Adapter.Out.Sse;
using Darueira.FoodMarket.Service06.Application;
using Darueira.FoodMarket.Service06.Port.In;
using Darueira.FoodMarket.Service06.Port.Out;
using Microsoft.OpenApi.Models;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();

var marketId = builder.Configuration["APP_MARKET_ID"] ?? "MKT-EU-06-DOTNET";

builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "Food Market 06 Service API (.NET 8 / C#)",
        Version = "v1",
        Description = $"Hexagonal Architecture REST API & SSE Stream for European Food Marketplaces in .NET 8 (Tenant: swfabrik-europe, Market: {marketId})"
    });
});

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod();
    });
});

// Dependency Injection (Hexagonal Architecture)
builder.Services.AddSingleton<IFoodTradingPersistencePort, PostgresFoodTradingAdapter>();
builder.Services.AddSingleton<IFoodTradingEventPublisherPort, RabbitMqPublisherAdapter>();
builder.Services.AddSingleton<IFoodTradingSseBroadcasterPort, SseBroadcasterAdapter>();
builder.Services.AddScoped<IFoodTradingUseCase, FoodTradingApplicationService>();
builder.Services.AddHostedService<RabbitMqConsumerBackgroundService>();

var app = builder.Build();

app.UseCors();

app.UseSwagger(c =>
{
    c.RouteTemplate = "v3/api-docs/{documentName}/swagger.json";
});
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/v3/api-docs/v1/swagger.json", "Food Market 06 Service v1");
    c.RoutePrefix = "swagger-ui";
});

app.MapGet("/healthz", () => Results.Ok(new { status = "UP", service = "food-market-06-service", tech = ".NET 8 / C#" }));

app.MapControllers();

app.Run();
