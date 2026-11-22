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
import jakarta.validation.Valid

@Tag(name = "Webhooks - Subscriptions", description = "Registration and lifecycle management of partner agency webhooks")
@SecurityRequirement(name = "BearerAuth")
@Controller("/webhooks/subscriptions")
@Secured(SecurityRule.IS_AUTHENTICATED)
@ExecuteOn(TaskExecutors.BLOCKING)
open class WebhookSubscriptionController(
    private val webhookSubscriptionService: WebhookSubscriptionService
) {

    @Operation(summary = "Get webhook subscription by ID", description = "Retrieves registration details for a specific webhook subscription")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Subscription found"),
        ApiResponse(responseCode = "404", description = "Subscription not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_GET permission")
    )
    @Get("/{id}")
    @NeedsPermission(Permission.WEBHOOK_GET)
    fun get(@PathVariable id: Long): WebhookSubscriptionResponse {
        val sub = webhookSubscriptionService.get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "WebhookSubscription not found: $id")
        return WebhookSubscriptionResponse.from(sub)
    }

    @Operation(summary = "List webhook subscriptions", description = "Lists active webhook subscriptions, optionally filtered by partnerAgencyId")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of webhook subscriptions"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_LIST permission")
    )
    @Get
    @NeedsPermission(Permission.WEBHOOK_LIST)
    fun list(@QueryValue partnerAgencyId: Long?): ListResult<WebhookSubscriptionResponse> {
        val subs = webhookSubscriptionService.list(partnerAgencyId)
        return ListResult(
            list = subs.map { WebhookSubscriptionResponse.from(it) },
            totalCount = subs.size.toLong()
        )
    }

    @Operation(summary = "Register a new webhook subscription", description = "Registers a partner agency webhook endpoint with HMAC secret and subscribed events")
    @ApiResponses(
        ApiResponse(responseCode = "201", description = "Webhook registered successfully"),
        ApiResponse(responseCode = "400", description = "Invalid URL or payload"),
        ApiResponse(responseCode = "404", description = "Partner agency not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_CREATE permission")
    )
    @Post
    @Status(HttpStatus.CREATED)
    @NeedsPermission(Permission.WEBHOOK_CREATE)
    fun create(@Body @Valid cmd: WebhookSubscriptionCommands.Create): WebhookSubscriptionResponse {
        val sub = webhookSubscriptionService.create(cmd)
        return WebhookSubscriptionResponse.from(sub)
    }

    @Operation(summary = "Update a webhook subscription", description = "Updates endpoint URL, secret, event filters, or status")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Webhook subscription updated"),
        ApiResponse(responseCode = "400", description = "Invalid URL or status"),
        ApiResponse(responseCode = "404", description = "Subscription not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_UPDATE permission")
    )
    @Put("/{id}")
    @NeedsPermission(Permission.WEBHOOK_UPDATE)
    fun update(@PathVariable id: Long, @Body cmd: WebhookSubscriptionCommands.Update): WebhookSubscriptionResponse {
        val sub = webhookSubscriptionService.update(id, cmd)
        return WebhookSubscriptionResponse.from(sub)
    }

    @Operation(summary = "Delete a webhook subscription", description = "Soft-deletes a webhook subscription to stop notifications")
    @ApiResponses(
        ApiResponse(responseCode = "204", description = "Subscription deleted successfully"),
        ApiResponse(responseCode = "404", description = "Subscription not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing WEBHOOK_DELETE permission")
    )
    @Delete("/{id}")
    @Status(HttpStatus.NO_CONTENT)
    @NeedsPermission(Permission.WEBHOOK_DELETE)
    fun delete(@PathVariable id: Long) {
        webhookSubscriptionService.delete(id)
    }
}
