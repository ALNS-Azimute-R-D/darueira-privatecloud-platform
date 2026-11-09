package com.darueira.foodmarket.service01.adapter.out.persistence;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface SpringDataFoodTradingRepository extends JpaRepository<FoodTradingJpaEntity, Long> {
    Optional<FoodTradingJpaEntity> findByTradingId(String tradingId);
}
