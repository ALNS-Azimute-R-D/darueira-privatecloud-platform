using System.Text;
using System.Text.Json;
using Darueira.FoodMarket.Service06.Domain.Events;
using Darueira.FoodMarket.Service06.Port.Out;
using RabbitMQ.Client;

namespace Darueira.FoodMarket.Service06.Adapter.Out.Messaging;

public class RabbitMqPublisherAdapter : IFoodTradingEventPublisherPort, IDisposable
{
    private readonly ILogger<RabbitMqPublisherAdapter> _logger;
    private readonly string _topicExchange;
    private IConnection? _connection;
    private IModel? _channel;
    private readonly ConnectionFactory _factory;

    public RabbitMqPublisherAdapter(IConfiguration config, ILogger<RabbitMqPublisherAdapter> logger)
    {
        _logger = logger;
        _topicExchange = config["APP_RABBITMQ_TOPIC"] ?? "marketplace.foodtrading.topic";

        var host = config["RABBITMQ_HOST"] ?? "message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local";
        var port = int.TryParse(config["RABBITMQ_PORT"], out var p) ? p : 5672;
        var user = config["RABBITMQ_USER"] ?? "drr_admin";
        var pass = config["RABBITMQ_PASS"] ?? "darueira-admin123";
        var vhost = config["RABBITMQ_VHOST"] ?? "/";

        _factory = new ConnectionFactory
        {
            HostName = host,
            Port = port,
            UserName = user,
            Password = pass,
            VirtualHost = vhost,
            DispatchConsumersAsync = true
        };

        InitConnection();
    }

    private void InitConnection()
    {
        try
        {
            _connection = _factory.CreateConnection();
            _channel = _connection.CreateModel();
            _channel.ExchangeDeclare(_topicExchange, ExchangeType.Topic, durable: true);
            _logger.LogInformation("[.NET 06] Connected RabbitMQ Publisher to exchange: {Exchange}", _topicExchange);
        }
        catch (Exception ex)
        {
            _logger.LogWarning("[.NET 06] Deferred RabbitMQ Publisher connection: {Message}", ex.Message);
        }
    }

    public Task PublishEventAsync(FoodTradingEvent tradingEvent, CancellationToken ct = default)
    {
        try
        {
            if (_channel == null || _channel.IsClosed)
            {
                InitConnection();
            }

            var routingKey = $"foodtrading.created.{tradingEvent.MarketId.ToLowerInvariant()}";
            var json = JsonSerializer.Serialize(new
            {
                eventId = tradingEvent.EventId,
                eventType = tradingEvent.EventType,
                tradingId = tradingEvent.TradingId,
                marketId = tradingEvent.MarketId,
                itemName = tradingEvent.ItemName,
                quantity = tradingEvent.Quantity,
                unitPrice = tradingEvent.UnitPrice,
                totalPrice = tradingEvent.TotalPrice,
                traderName = tradingEvent.TraderName,
                status = tradingEvent.Status,
                timestamp = tradingEvent.Timestamp.ToString("o")
            });

            var body = Encoding.UTF8.GetBytes(json);
            var props = _channel!.CreateBasicProperties();
            props.ContentType = "application/json";
            props.DeliveryMode = 2; // persistent

            _channel.BasicPublish(
                exchange: _topicExchange,
                routingKey: routingKey,
                basicProperties: props,
                body: body
            );

            _logger.LogInformation("[.NET 06] Published event to RabbitMQ topic {Topic} [{RoutingKey}]: {TradingId}", _topicExchange, routingKey, tradingEvent.TradingId);
        }
        catch (Exception ex)
        {
            _logger.LogError("[.NET 06] Failed to publish message: {Message}", ex.Message);
        }

        return Task.CompletedTask;
    }

    public void Dispose()
    {
        _channel?.Dispose();
        _connection?.Dispose();
    }
}
