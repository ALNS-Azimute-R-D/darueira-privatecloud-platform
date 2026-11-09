package messaging

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	"github.com/darueira/foodmarket/service03/internal/domain"
	amqp "github.com/rabbitmq/amqp091-go"
)

type RabbitMQPublisher struct {
	amqpURI       string
	topicExchange string
	conn          *amqp.Connection
	channel       *amqp.Channel
	mu            sync.Mutex
}

func NewRabbitMQPublisher(amqpURI, topicExchange string) *RabbitMQPublisher {
	p := &RabbitMQPublisher{
		amqpURI:       amqpURI,
		topicExchange: topicExchange,
	}
	_ = p.connect()
	return p
}

func (p *RabbitMQPublisher) connect() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	conn, err := amqp.Dial(p.amqpURI)
	if err != nil {
		return err
	}
	ch, err := conn.Channel()
	if err != nil {
		conn.Close()
		return err
	}

	err = ch.ExchangeDeclare(
		p.topicExchange,
		"topic",
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		ch.Close()
		conn.Close()
		return err
	}

	p.conn = conn
	p.channel = ch
	log.Printf("[Go 03] Connected RabbitMQ Publisher to exchange: %s", p.topicExchange)
	return nil
}

func (p *RabbitMQPublisher) PublishEvent(ctx context.Context, event domain.FoodTradingEvent) error {
	if p.channel == nil || p.conn == nil || p.conn.IsClosed() {
		if err := p.connect(); err != nil {
			return fmt.Errorf("failed to reconnect publisher: %w", err)
		}
	}

	routingKey := fmt.Sprintf("foodtrading.created.%s", strings.ToLower(event.MarketID))
	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}

	err = p.channel.PublishWithContext(
		ctx,
		p.topicExchange,
		routingKey,
		false,
		false,
		amqp.Publishing{
			ContentType: "application/json",
			Body:        payload,
			Timestamp:   time.Now().UTC(),
		},
	)
	if err != nil {
		return fmt.Errorf("failed to publish AMQP message: %w", err)
	}

	log.Printf("[Go 03] Published event to RabbitMQ topic %s [%s]: %s", p.topicExchange, routingKey, event.TradingID)
	return nil
}

func (p *RabbitMQPublisher) Close() {
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.channel != nil {
		p.channel.Close()
	}
	if p.conn != nil {
		p.conn.Close()
	}
}
