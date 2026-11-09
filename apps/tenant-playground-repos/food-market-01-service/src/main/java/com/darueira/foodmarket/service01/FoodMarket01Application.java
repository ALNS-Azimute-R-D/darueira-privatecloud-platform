package com.darueira.foodmarket.service01;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class FoodMarket01Application {

    public static void main(String[] args) {
        SpringApplication.run(FoodMarket01Application.class, args);
    }
}
