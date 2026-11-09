package sse

import (
	"log"
	"sync"

	"github.com/darueira/foodmarket/service03/internal/domain"
)

type Broadcaster struct {
	clients map[chan domain.FoodTrading]bool
	mu      sync.RWMutex
}

func NewBroadcaster() *Broadcaster {
	return &Broadcaster{
		clients: make(map[chan domain.FoodTrading]bool),
	}
}

func (b *Broadcaster) Subscribe() <-chan domain.FoodTrading {
	b.mu.Lock()
	defer b.mu.Unlock()
	ch := make(chan domain.FoodTrading, 50)
	b.clients[ch] = true
	log.Printf("[Go 03] SSE client connected (Total active: %d)", len(b.clients))
	return ch
}

func (b *Broadcaster) Unsubscribe(ch <-chan domain.FoodTrading) {
	b.mu.Lock()
	defer b.mu.Unlock()
	for c := range b.clients {
		if c == ch {
			delete(b.clients, c)
			close(c)
			log.Printf("[Go 03] SSE client disconnected (Total active: %d)", len(b.clients))
			break
		}
	}
}

func (b *Broadcaster) Broadcast(trading domain.FoodTrading) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	log.Printf("[Go 03] Broadcasting food trading via SSE to %d active clients: %s", len(b.clients), trading.TradingID)
	for ch := range b.clients {
		select {
		case ch <- trading:
		default:
			log.Printf("[Go 03] Buffer full, dropped SSE message for slow client")
		}
	}
}
