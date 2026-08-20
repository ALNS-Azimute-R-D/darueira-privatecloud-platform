using System.Text;
using System.Text.Json;
using Darueira.FoodMarket.Service06.Domain.Events;
using Darueira.FoodMarket.Service06.Port.In;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

namespace Darueira.FoodMarket.Service06.Adapter.In.Messaging;

public class RabbitMqConsumerBackgroundService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<RabbitMqConsumerBackgroundService> _logger;
    private readonly IConfiguration _config;
    private IConnection? _connection;
    private IModel? _channel;

    public RabbitMqConsumerBackgroundService(
        IServiceProvider serviceProvider,
        ILogger<RabbitMqConsumerBackgroundService> logger,
        IConfiguration config)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
        _config = config;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var topicExchange = _config["APP_RABBITMQ_TOPIC"] ?? "marketplace.foodtrading.topic";
        var queueName = _config["APP_RABBITMQ_QUEUE"] ?? "marketplace.foodtrading.queue06";
        var host = _config["RABBITMQ_HOST"] ?? "message-broker-rabbitmq.drr-corpshared-plat.svc.cluster.local";
        var port = int.TryParse(_config["RABBITMQ_PORT"], out var p) ? p : 5672;
        var user = _config["RABBITMQ_USER"] ?? "drr_admin";
        var pass = _config["RABBITMQ_PASS"] ?? "darueira-admin123";
        var vhost = _config["RABBITMQ_VHOST"] ?? "/";

        var factory = new ConnectionFactory
        {
            HostName = host,
            Port = port,
            UserName = user,
            Password = pass,
            VirtualHost = vhost,
            DispatchConsumersAsync = true
        };

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                _connection = factory.CreateConnection();
                _channel = _connection.CreateModel();
                _channel.ExchangeDeclare(exchange: topicExchange, type: ExchangeType.Topic, durable: true);
                _channel.QueueDeclare(queue: queueName, durable: true, exclusive: false, autoDelete: false, arguments: null);
                _channel.QueueBind(queue: queueName, exchange: topicExchange, routingKey: "#");

                var consumer = new AsyncEventingBasicConsumer(_channel);
                consumer.Received += async (model, ea) =>
                {
                    try
                    {
                        var body = ea.Body.ToArray();
                        var message = Encoding.UTF8.GetString(body);
                        _logger.LogInformation("[.NET 06] Consumed message from queue {Queue}: {Body}", queueName, message);

                        var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                        var tradingEvent = JsonSerializer.Deserialize<FoodTradingEvent>(message, options);
                        if (tradingEvent != null)
                        {
                            _logger.LogInformation("[.NET 06] Consumed message from queue {Queue}: {TradingId}", queueName, tradingEvent.TradingId);

                            using var scope = _serviceProvider.CreateScope();
                            var useCase = scope.ServiceProvider.GetRequiredService<IFoodTradingUseCase>();
                            await useCase.ProcessIncomingEventAsync(tradingEvent, stoppingToken);
                        }

                        _channel.BasicAck(ea.DeliveryTag, false);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError("[.NET 06] Error processing message: {Message}", ex.Message);
                        _channel.BasicNack(ea.DeliveryTag, false, false);
                    }
                };

                _channel.BasicConsume(queue: queueName, autoAck: false, consumer: consumer);
                _logger.LogInformation("[.NET 06] RabbitMQ Consumer listening on queue: {Queue}", queueName);

                await Task.Delay(Timeout.Infinite, stoppingToken);
            }
            catch (Exception ex) when (!stoppingToken.IsCancellationRequested)
            {
                _logger.LogWarning("[.NET 06] Consumer disconnected: {Message}. Retrying in 2s...", ex.Message);
                await Task.Delay(2000, stoppingToken);
            }
        }
    }

    public override void Dispose()
    {
        _channel?.Dispose();
        _connection?.Dispose();
        base.Dispose();
    }
}
