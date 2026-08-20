package com.darueira.foodmarket.service02.adapter.`in`.rest

import com.darueira.foodmarket.service02.domain.model.CreateFoodTradingCommand
import com.darueira.foodmarket.service02.domain.port.`in`.FoodTradingUseCase
import io.smallrye.mutiny.Multi
import jakarta.enterprise.context.ApplicationScoped
import jakarta.ws.rs.*
import jakarta.ws.rs.core.MediaType
import jakarta.ws.rs.core.Response
import org.eclipse.microprofile.openapi.annotations.Operation
import org.eclipse.microprofile.openapi.annotations.tags.Tag
import org.jboss.resteasy.reactive.RestStreamElementType
import java.math.BigDecimal
import java.time.Instant

@Path("/api/food-tradings")
@ApplicationScoped
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
@Tag(name = "Food Tradings API (Quarkus)", description = "Kotlin / Quarkus Reactive Food Trading Endpoints")
class FoodTradingResource(
    private val useCase: FoodTradingUseCase
) {

    @POST
    @Operation(summary = "Create Food Trading", description = "F01.1: Creates a new food trading entry in Quarkus, persists to DB and publishes to RabbitMQ topic")
    fun createTrading(request: CreateTradingRequest): Response {
        val command = CreateFoodTradingCommand(
            itemName = request.itemName,
            quantity = request.quantity,
            unitPrice = request.unitPrice,
            traderName = request.traderName
        )
        val created = useCase.createTrading(command)
        return Response.status(Response.Status.CREATED).entity(FoodTradingResponse.fromDomain(created)).build()
    }

    @GET
    @Operation(summary = "List Food Tradings", description = "F01.2: Lists all food tradings from Quarkus PostgreSQL schema schm02")
    fun listTradings(): List<FoodTradingResponse> {
        return useCase.listTradings().map { FoodTradingResponse.fromDomain(it) }
    }

    @GET
    @Path("/stream")
    @Produces(MediaType.SERVER_SENT_EVENTS)
    @RestStreamElementType(MediaType.APPLICATION_JSON)
    @Operation(summary = "Stream Food Tradings", description = "F01.3: Real-Time Server-Sent Events (SSE) Stream from Quarkus Mutiny")
    fun streamTradings(): Multi<FoodTradingResponse> {
        val initial = FoodTradingResponse(
            id = 0,
            tradingId = "INIT",
            marketId = "MKT-EU-02-QUARKUS",
            itemName = "Connected",
            quantity = BigDecimal.ZERO,
            unitPrice = BigDecimal.ZERO,
            totalPrice = BigDecimal.ZERO,
            traderName = "System",
            status = "INIT",
            createdAt = Instant.now()
        )
        val pings = Multi.createFrom().ticks().every(java.time.Duration.ofSeconds(10))
            .map {
                FoodTradingResponse(
                    id = 0,
                    tradingId = "PING",
                    marketId = "MKT-EU-02-QUARKUS",
                    itemName = "ping",
                    quantity = BigDecimal.ZERO,
                    unitPrice = BigDecimal.ZERO,
                    totalPrice = BigDecimal.ZERO,
                    traderName = "System",
                    status = "PING",
                    createdAt = Instant.now()
                )
            }
        val dataEvents = useCase.subscribeStream().map { FoodTradingResponse.fromDomain(it) }
        return Multi.createBy().merging().streams(
            Multi.createFrom().item(initial),
            pings,
            dataEvents
        )
    }
}
