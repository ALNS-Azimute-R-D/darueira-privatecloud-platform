package de.legalhub.domains.legalcase

import de.legalhub.domains.auth.NeedsPermission
import de.legalhub.domains.auth.Permission
import de.legalhub.model.ListResult
import de.legalhub.model.UserRole
import io.micronaut.http.HttpStatus
import io.micronaut.http.annotation.Body
import io.micronaut.http.annotation.Controller
import io.micronaut.http.annotation.Get
import io.micronaut.http.annotation.PathVariable
import io.micronaut.http.annotation.Post
import io.micronaut.http.annotation.Put
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

@Tag(name = "Legal Cases", description = "Management of legal cases for law firms and partner agencies")
@SecurityRequirement(name = "BearerAuth")
@Controller("/cases")
@Secured(SecurityRule.IS_AUTHENTICATED)
@ExecuteOn(TaskExecutors.BLOCKING)
open class LegalCaseController(
    private val legalCaseService: LegalCaseService,
) {

    @Operation(summary = "Get legal case by ID", description = "Retrieves details of a single legal case by its identifier")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Legal case found and returned"),
        ApiResponse(responseCode = "404", description = "Legal case not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing CASE_GET permission")
    )
    @Get("/{id}")
    @NeedsPermission(Permission.CASE_GET)
    fun get(@PathVariable id: Long): LegalCaseResponse {
        val legalCase = legalCaseService.get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "LegalCase not found")
        return LegalCaseResponse.from(legalCase)
    }

    @Operation(summary = "List legal cases", description = "Lists all non-deleted legal cases")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of legal cases returned"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing CASE_LIST permission")
    )
    @Get
    @NeedsPermission(Permission.CASE_LIST)
    fun list(): ListResult<LegalCaseResponse> {
        val cases = legalCaseService.list()
        return ListResult(
            list = cases.map { LegalCaseResponse.from(it) },
            totalCount = cases.size.toLong()
        )
    }

    @Operation(summary = "Create a legal case", description = "Creates a new legal case and emits a real-time entity event")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Legal case created successfully"),
        ApiResponse(responseCode = "400", description = "Invalid input payload"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing CASE_CREATE permission")
    )
    @Post
    @NeedsPermission(Permission.CASE_CREATE)
    fun create(@Body cmd: LegalCaseCommands.Create): LegalCaseResponse {
        val legalCase = legalCaseService.create(cmd)
        return LegalCaseResponse.from(legalCase)
    }

    @Operation(summary = "Update a legal case", description = "Updates an existing legal case and emits a real-time entity event")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Legal case updated successfully"),
        ApiResponse(responseCode = "404", description = "Legal case not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing CASE_UPDATE permission")
    )
    @Put("/{id}")
    @NeedsPermission(Permission.CASE_UPDATE)
    fun update(@PathVariable id: Long, @Body cmd: LegalCaseCommands.Update): LegalCaseResponse {
        val legalCase = legalCaseService.update(id, cmd)
        return LegalCaseResponse.from(legalCase)
    }
}

