package de.legalhub.domains.webhook

import de.legalhub.domains.auth.NeedsPermission
import de.legalhub.domains.auth.Permission
import de.legalhub.model.ListResult
import de.legalhub.model.UserRole
import io.micronaut.http.HttpStatus
import io.micronaut.http.annotation.*
import io.micronaut.http.exceptions.HttpStatusException
import io.micronaut.scheduling.TaskExecutors
import io.micronaut.scheduling.annotation.ExecuteOn
import io.micronaut.security.annotation.Secured
import io.micronaut.security.rules.SecurityRule
import io.swagger.v3.oas.annotations.Operation
import io.swagger.v3.oas.annotations.responses.ApiResponse
import io.swagger.v3.oas.annotations.responses.ApiResponses
import io.swagger.v3.oas.annotations.security.SecurityRequirement
import io.swagger.v3.oas.annotations.tags.Tag

@Tag(name = "Webhooks - Deliveries", description = "Audit logs and manual retry management for webhook deliveries")
@SecurityRequirement(name = "BearerAuth")
@Controller("/webhooks/deliveries")
@Secured(SecurityRule.IS_AUTHENTICATED)
@ExecuteOn(TaskExecutors.BLOCKING)
open class WebhookDeliveryController(
    private val webhookDeliveryService: WebhookDeliveryService
) {

    @Operation(summary = "Get delivery attempt by ID", description = "Retrieves execution log, status, and response details for a specific webhook delivery")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Delivery record found"),
        ApiResponse(responseCode = "404", description = "Delivery record not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_GET permission")
    )
    @Get("/{id}")
    @NeedsPermission(Permission.WEBHOOK_GET)
    fun get(@PathVariable id: Long): WebhookDeliveryResponse {
        val delivery = webhookDeliveryService.get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "WebhookDelivery not found: $id")
        return WebhookDeliveryResponse.from(delivery)
    }

    @Operation(summary = "List deliveries by subscription ID", description = "Lists all delivery attempts for a given webhook subscription")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of delivery attempts"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_LIST permission")
    )
    @Get
    @NeedsPermission(Permission.WEBHOOK_LIST)
    fun listBySubscription(@QueryValue subscriptionId: Long): ListResult<WebhookDeliveryResponse> {
        val deliveries = webhookDeliveryService.listBySubscription(subscriptionId)
        return ListResult(
            list = deliveries.map { WebhookDeliveryResponse.from(it) },
            totalCount = deliveries.size.toLong()
        )
    }

    @Operation(summary = "Manually retry a failed delivery", description = "Re-triggers an HTTP delivery attempt for an existing webhook delivery record")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Delivery retried"),
        ApiResponse(responseCode = "404", description = "Delivery record not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_UPDATE permission")
    )
    @Post("/{id}/retry")
    @NeedsPermission(Permission.WEBHOOK_UPDATE)
    fun retry(@PathVariable id: Long): WebhookDeliveryResponse {
        val delivery = webhookDeliveryService.retry(id)
        return WebhookDeliveryResponse.from(delivery)
    }
}
