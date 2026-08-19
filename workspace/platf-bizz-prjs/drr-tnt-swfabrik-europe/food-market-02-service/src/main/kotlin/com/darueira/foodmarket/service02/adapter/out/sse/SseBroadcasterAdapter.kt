package com.darueira.foodmarket.service02.adapter.out.sse

import com.darueira.foodmarket.service02.domain.model.FoodTrading
import com.darueira.foodmarket.service02.domain.port.out.FoodTradingSseBroadcasterPort
import io.smallrye.mutiny.Multi
import io.smallrye.mutiny.operators.multi.processors.BroadcastProcessor
import jakarta.enterprise.context.ApplicationScoped
import org.jboss.logging.Logger

@ApplicationScoped
class SseBroadcasterAdapter : FoodTradingSseBroadcasterPort {

    private val log = Logger.getLogger(SseBroadcasterAdapter::class.java)
    private val processor: BroadcastProcessor<FoodTrading> = BroadcastProcessor.create()

    override fun stream(): Multi<FoodTrading> {
        return processor
    }

    override fun broadcast(trading: FoodTrading) {
        log.infof("[Kotlin/Quarkus 02] Broadcasting SSE trading event: %s", trading.tradingId)
        processor.onNext(trading)
    }
}
