package de.legalhub.domains.partneragency

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

@Tag(name = "Partner Agencies", description = "Onboarding, lifecycle management, and querying of Legal Partner Agencies")
@SecurityRequirement(name = "BearerAuth")
@Controller("/partner-agencies")
@Secured(SecurityRule.IS_AUTHENTICATED)
@Consumes(io.micronaut.http.MediaType.APPLICATION_JSON)
@Produces(io.micronaut.http.MediaType.APPLICATION_JSON)
@ExecuteOn(TaskExecutors.BLOCKING)
open class PartnerAgencyController(
    private val partnerAgencyService: PartnerAgencyService
) {

    @Operation(
        summary = "Onboard a new Partner Agency",
        description = "Registers a new Partner Agency and atomically provisions its initial collection of webhook subscriptions, legal cases, users, and actions"
    )
    @ApiResponses(
        ApiResponse(responseCode = "201", description = "Partner Agency onboarded successfully with webhooks, cases, and actions"),
        ApiResponse(responseCode = "400", description = "Invalid payload or unresolvable webhook target URL"),
        ApiResponse(responseCode = "409", description = "Partner Agency alias already exists"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing AGENCY_CREATE permission")
    )
    @Post("/onboarding")
    @Status(HttpStatus.CREATED)
    @NeedsPermission(Permission.AGENCY_CREATE)
    fun onboard(@Body @Valid cmd: PartnerAgencyOnboardingCommand): PartnerAgencyResponse {
        return partnerAgencyService.onboard(cmd)
    }

    @Operation(
        summary = "Batch Onboard Partner Agencies",
        description = "Registers a batch collection of Partner Agencies and atomically provisions their webhooks, legal cases, users, and actions"
    )
    @ApiResponses(
        ApiResponse(responseCode = "201", description = "Partner Agencies onboarded successfully"),
        ApiResponse(responseCode = "400", description = "Invalid payload or unresolvable webhook target URL"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing AGENCY_CREATE permission")
    )
    @Post("/batch-onboarding")
    @Status(HttpStatus.CREATED)
    @NeedsPermission(Permission.AGENCY_CREATE)
    fun batchOnboard(@Body @Valid cmd: PartnerAgencyBatchOnboardingCommand): List<PartnerAgencyResponse> {
        return partnerAgencyService.onboardBatch(cmd)
    }

    @Post("/onboarding/batch")
    @Status(HttpStatus.CREATED)
    @NeedsPermission(Permission.AGENCY_CREATE)
    fun onboardingBatchAlias(@Body @Valid cmd: PartnerAgencyBatchOnboardingCommand): List<PartnerAgencyResponse> {
        return partnerAgencyService.onboardBatch(cmd)
    }

    @Operation(
        summary = "Create Partner Agency",
        description = "Alternative alias endpoint for onboarding a new Partner Agency"
    )
    @ApiResponses(
        ApiResponse(responseCode = "201", description = "Partner Agency onboarded successfully"),
        ApiResponse(responseCode = "409", description = "Partner Agency alias already exists")
    )
    @Post
    @Status(HttpStatus.CREATED)
    @NeedsPermission(Permission.AGENCY_CREATE)
    fun create(@Body @Valid cmd: PartnerAgencyOnboardingCommand): PartnerAgencyResponse {
        return partnerAgencyService.onboard(cmd)
    }

    @Operation(
        summary = "Get Partner Agency by ID",
        description = "Retrieves agency details along with all active webhook subscriptions"
    )
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Partner agency found"),
        ApiResponse(responseCode = "404", description = "Partner agency not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing AGENCY_GET permission")
    )
    @Get("/{id}")
    @NeedsPermission(Permission.AGENCY_GET)
    fun get(@PathVariable id: Long): PartnerAgencyResponse {
        return partnerAgencyService.getWithWebhooks(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "PartnerAgency not found: $id")
    }

    @Operation(
        summary = "Get Partner Agency by Alias",
        description = "Retrieves agency details by unique alias / slug along with its active webhook subscriptions"
    )
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Partner agency found"),
        ApiResponse(responseCode = "404", description = "Partner agency not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing AGENCY_GET permission")
    )
    @Get("/by-alias/{alias}")
    @NeedsPermission(Permission.AGENCY_GET)
    fun getByAlias(@PathVariable alias: String): PartnerAgencyResponse {
        return partnerAgencyService.getByAliasWithWebhooks(alias)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "PartnerAgency with alias not found: $alias")
    }

    @Operation(
        summary = "List Partner Agencies",
        description = "Lists all registered partner agencies"
    )
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of partner agencies"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing AGENCY_LIST permission")
    )
    @Get
    @NeedsPermission(Permission.AGENCY_LIST)
    fun list(): ListResult<PartnerAgencyResponse> {
        val agencies = partnerAgencyService.list()
        return ListResult(
            list = agencies.map { PartnerAgencyResponse.from(it) },
            totalCount = agencies.size.toLong()
        )
    }
}
