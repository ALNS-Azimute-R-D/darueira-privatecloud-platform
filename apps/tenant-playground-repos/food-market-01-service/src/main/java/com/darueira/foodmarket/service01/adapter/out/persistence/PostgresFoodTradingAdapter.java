package com.darueira.foodmarket.service01.adapter.out.persistence;

import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import com.darueira.foodmarket.service01.domain.port.out.FoodTradingPersistencePort;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

@Component
public class PostgresFoodTradingAdapter implements FoodTradingPersistencePort {

    private final SpringDataFoodTradingRepository repository;

    public PostgresFoodTradingAdapter(SpringDataFoodTradingRepository repository) {
        this.repository = repository;
    }

    @Override
    public FoodTrading save(FoodTrading trading) {
        FoodTradingJpaEntity entity = FoodTradingJpaEntity.fromDomain(trading);
        FoodTradingJpaEntity saved = repository.save(entity);
        return saved.toDomain();
    }

    @Override
    public List<FoodTrading> findAll() {
        return repository.findAll().stream()
                .map(FoodTradingJpaEntity::toDomain)
                .collect(Collectors.toList());
    }

    @Override
    public Optional<FoodTrading> findByTradingId(String tradingId) {
        return repository.findByTradingId(tradingId)
                .map(FoodTradingJpaEntity::toDomain);
    }
}
