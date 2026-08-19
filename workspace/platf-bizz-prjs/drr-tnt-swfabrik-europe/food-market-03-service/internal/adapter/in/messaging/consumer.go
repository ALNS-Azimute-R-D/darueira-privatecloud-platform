package messaging

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/darueira/foodmarket/service03/internal/domain"
	"github.com/darueira/foodmarket/service03/internal/port"
	amqp "github.com/rabbitmq/amqp091-go"
)

type RabbitMQConsumer struct {
	amqpURI   string
	queueName string
	useCase   port.FoodTradingUseCase
	stopChan  chan struct{}
}

func NewRabbitMQConsumer(amqpURI, queueName string, useCase port.FoodTradingUseCase) *RabbitMQConsumer {
	return &RabbitMQConsumer{
		amqpURI:   amqpURI,
		queueName: queueName,
		useCase:   useCase,
		stopChan:  make(chan struct{}),
	}
}

func (c *RabbitMQConsumer) Start(ctx context.Context) {
	go func() {
		for {
			select {
			case <-c.stopChan:
				return
			case <-ctx.Done():
				return
			default:
				if err := c.run(ctx); err != nil {
					log.Printf("[Go 03] RabbitMQ Consumer disconnected: %v. Retrying in 2s...", err)
					time.Sleep(2 * time.Second)
				}
			}
		}
	}()
}

func (c *RabbitMQConsumer) run(ctx context.Context) error {
	conn, err := amqp.Dial(c.amqpURI)
	if err != nil {
		return err
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		return err
	}
	defer ch.Close()

	_, err = ch.QueueDeclare(
		c.queueName,
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		return err
	}

	msgs, err := ch.Consume(
		c.queueName,
		"",
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		return err
	}

	log.Printf("[Go 03] RabbitMQ Consumer listening on queue: %s", c.queueName)

	for {
		select {
		case <-c.stopChan:
			return nil
		case <-ctx.Done():
			return nil
		case msg, ok := <-msgs:
			if !ok {
				return nil
			}
			log.Printf("[Go 03] Consumed message from queue %s: %s", c.queueName, string(msg.Body))
			var event domain.FoodTradingEvent
			if err := json.Unmarshal(msg.Body, &event); err != nil {
				log.Printf("[Go 03] Failed to deserialize message: %v", err)
				continue
			}
			if err := c.useCase.ProcessIncomingEvent(ctx, event); err != nil {
				log.Printf("[Go 03] Failed to process event: %v", err)
			}
		}
	}
}

func (c *RabbitMQConsumer) Stop() {
	close(c.stopChan)
}
