package port

import (
	"context"
	"github.com/darueira/foodmarket/service03/internal/domain"
)

type FoodTradingUseCase interface {
	CreateTrading(ctx context.Context, cmd domain.CreateFoodTradingCommand) (*domain.FoodTrading, error)
	ListTradings(ctx context.Context) ([]domain.FoodTrading, error)
	SubscribeStream() <-chan domain.FoodTrading
	UnsubscribeStream(ch <-chan domain.FoodTrading)
	ProcessIncomingEvent(ctx context.Context, event domain.FoodTradingEvent) error
}

type FoodTradingPersistencePort interface {
	Save(ctx context.Context, trading *domain.FoodTrading) (*domain.FoodTrading, error)
	FindAll(ctx context.Context) ([]domain.FoodTrading, error)
	FindByTradingID(ctx context.Context, tradingID string) (*domain.FoodTrading, error)
}

type FoodTradingEventPublisherPort interface {
	PublishEvent(ctx context.Context, event domain.FoodTradingEvent) error
}

type FoodTradingSseBroadcasterPort interface {
	Subscribe() <-chan domain.FoodTrading
	Unsubscribe(ch <-chan domain.FoodTrading)
	Broadcast(trading domain.FoodTrading)
}
