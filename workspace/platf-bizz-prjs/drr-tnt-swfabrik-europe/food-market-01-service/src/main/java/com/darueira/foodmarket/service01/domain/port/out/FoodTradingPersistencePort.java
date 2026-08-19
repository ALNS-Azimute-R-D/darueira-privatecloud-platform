package com.darueira.foodmarket.service01.domain.port.out;

import com.darueira.foodmarket.service01.domain.model.FoodTrading;

import java.util.List;
import java.util.Optional;

public interface FoodTradingPersistencePort {
    FoodTrading save(FoodTrading trading);
    List<FoodTrading> findAll();
    Optional<FoodTrading> findByTradingId(String tradingId);
}
