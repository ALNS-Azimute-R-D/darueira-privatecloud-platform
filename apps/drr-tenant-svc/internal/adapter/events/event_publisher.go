package events

import (
	"encoding/json"
	"fmt"

	"github.com/dexterity/darueira/apps/drr-tenant-svc/internal/domain"
)

type LoggingEventPublisher struct {
	topic string
}

func NewLoggingEventPublisher(topic string) *LoggingEventPublisher {
	if topic == "" {
		topic = "drr.tenant.events"
	}
	return &LoggingEventPublisher{topic: topic}
}

func (p *LoggingEventPublisher) Publish(event domain.DomainEvent) error {
	data, err := json.Marshal(event)
	if err != nil {
		return err
	}
	fmt.Printf("[KAFKA-PRODUCER] [%s] %s\n", p.topic, string(data))
	return nil
}
