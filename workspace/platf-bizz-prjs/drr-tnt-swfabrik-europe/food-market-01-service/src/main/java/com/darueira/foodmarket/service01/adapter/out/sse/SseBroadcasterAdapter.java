package com.darueira.foodmarket.service01.adapter.out.sse;

import com.darueira.foodmarket.service01.domain.model.FoodTrading;
import com.darueira.foodmarket.service01.domain.port.out.FoodTradingSseBroadcasterPort;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

@Component
public class SseBroadcasterAdapter implements FoodTradingSseBroadcasterPort {

    private static final Logger log = LoggerFactory.getLogger(SseBroadcasterAdapter.class);

    private final List<SseEmitter> emitters = new CopyOnWriteArrayList<>();

    @Override
    public SseEmitter registerClient() {
        // 30 minutes timeout
        SseEmitter emitter = new SseEmitter(1800_000L);
        emitters.add(emitter);

        emitter.onCompletion(() -> {
            log.debug("SSE client completed connection");
            emitters.remove(emitter);
        });

        emitter.onTimeout(() -> {
            log.debug("SSE client timed out");
            emitter.complete();
            emitters.remove(emitter);
        });

        emitter.onError(e -> {
            log.debug("SSE client connection error: {}", e.getMessage());
            emitters.remove(emitter);
        });

        try {
            // Send initial connection heartbeat
            emitter.send(SseEmitter.event()
                    .name("INIT")
                    .data("Connected to Food Trading Live SSE Stream (Service 01 - Java/Spring)"));
        } catch (IOException e) {
            emitters.remove(emitter);
        }

        return emitter;
    }

    @Override
    public void broadcast(FoodTrading trading) {
        log.info("[Spring Boot 01] Broadcasting food trading via SSE to {} active clients: {}", emitters.size(), trading.getTradingId());
        List<SseEmitter> deadEmitters = new CopyOnWriteArrayList<>();

        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(SseEmitter.event()
                        .name("FOOD_TRADING_EVENT")
                        .data(trading));
            } catch (Exception e) {
                deadEmitters.add(emitter);
            }
        }
        emitters.removeAll(deadEmitters);
    }
}
