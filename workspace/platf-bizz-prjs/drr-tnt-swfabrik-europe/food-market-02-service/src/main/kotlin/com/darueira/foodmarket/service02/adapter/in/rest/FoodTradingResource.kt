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
    @Operation(summary = "Stream Food Tradings", description = "F01.3: Real-Time Server-Sent Events (SSE) Stream from Quarkus Mutiny")
    fun streamTradings(@jakarta.ws.rs.core.Context sse: jakarta.ws.rs.sse.Sse): Multi<jakarta.ws.rs.sse.OutboundSseEvent> {
        val initEvent = sse.newEventBuilder()
            .name("INIT")
            .data("Connected to Food Trading Live SSE Stream (Service 02 - Kotlin/Quarkus)")
            .build()

        val dataStream = useCase.subscribeStream().map {
            sse.newEventBuilder()
                .name("FOOD_TRADING_EVENT")
                .mediaType(MediaType.APPLICATION_JSON_TYPE)
                .data(FoodTradingResponse.fromDomain(it))
                .build()
        }

        return Multi.createFrom().item(initEvent).onCompletion().switchTo(dataStream)
    }
}
