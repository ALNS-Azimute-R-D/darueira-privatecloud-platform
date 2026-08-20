package com.darueira.foodmarket.service01.adapter.in.rest;

import com.darueira.foodmarket.service01.domain.model.CreateFoodTradingCommand;
import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import com.darueira.foodmarket.service01.domain.port.in.FoodTradingUseCase;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/food-tradings")
@CrossOrigin(origins = "*")
@Tag(name = "Food Tradings API", description = "Endpoints for European Food Trading & Real-Time Stream")
public class FoodTradingRestController {

    private final FoodTradingUseCase useCase;

    public FoodTradingRestController(FoodTradingUseCase useCase) {
        this.useCase = useCase;
    }

    @PostMapping(consumes = MediaType.APPLICATION_JSON_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    @Operation(summary = "Create Food Trading", description = "F01.1: Creates a new food trading entry, persists to DB and publishes to RabbitMQ topic")
    public ResponseEntity<FoodTradingResponse> createTrading(@Valid @RequestBody CreateTradingRequest request) {
        CreateFoodTradingCommand command = CreateFoodTradingCommand.builder()
                .itemName(request.getItemName())
                .quantity(request.getQuantity())
                .unitPrice(request.getUnitPrice())
                .traderName(request.getTraderName())
                .build();

        FoodTrading created = useCase.createTrading(command);
        return ResponseEntity.status(HttpStatus.CREATED).body(FoodTradingResponse.fromDomain(created));
    }

    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    @Operation(summary = "List Food Tradings", description = "F01.2: Returns all confirmed food tradings from the database")
    public ResponseEntity<List<FoodTradingResponse>> listTradings() {
        List<FoodTradingResponse> list = useCase.listTradings().stream()
                .map(FoodTradingResponse::fromDomain)
                .collect(Collectors.toList());
        return ResponseEntity.ok(list);
    }

    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(summary = "Subscribe Food Tradings Stream", description = "F01.3: Real-Time Server-Sent Events (SSE) stream for consumed food trading events")
    public SseEmitter streamTradings() {
        return useCase.subscribeStream();
    }
}
