package de.legalhub.domains.bulk

import de.legalhub.domains.auth.NeedsPermission
import de.legalhub.domains.auth.Permission
import de.legalhub.model.UserRole
import de.legalhub.adapters.output.repository.UserRepository
import io.micronaut.http.HttpStatus
import io.micronaut.http.annotation.*
import io.micronaut.http.exceptions.HttpStatusException
import io.micronaut.scheduling.TaskExecutors
import io.micronaut.scheduling.annotation.ExecuteOn
import io.micronaut.security.annotation.Secured
import io.micronaut.security.authentication.Authentication
import io.micronaut.security.rules.SecurityRule
import io.swagger.v3.oas.annotations.Operation
import io.swagger.v3.oas.annotations.responses.ApiResponse
import io.swagger.v3.oas.annotations.responses.ApiResponses
import io.swagger.v3.oas.annotations.security.SecurityRequirement
import io.swagger.v3.oas.annotations.tags.Tag
import jakarta.validation.Valid

@Tag(name = "Bulk Operations", description = "High-throughput asynchronous batch operations and case reassignment")
@SecurityRequirement(name = "BearerAuth")
@Controller("/cases/bulk-reassign")
@Secured(SecurityRule.IS_AUTHENTICATED)
@ExecuteOn(TaskExecutors.BLOCKING)
open class BulkOperationController(
    private val bulkOperationService: BulkOperationService,
    private val userRepository: UserRepository
) {

    @Operation(summary = "Execute bulk case reassignment", description = "Reassigns multiple cases to a target lawyer matching filter criteria and triggers event updates")
    @ApiResponses(
        ApiResponse(responseCode = "202", description = "Bulk reassignment job accepted and executed"),
        ApiResponse(responseCode = "400", description = "Invalid criteria or missing targetLawyerId"),
        ApiResponse(responseCode = "404", description = "Target lawyer not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing BULK_OPERATION_CREATE permission")
    )
    @Post
    @Status(HttpStatus.ACCEPTED)
    @NeedsPermission(Permission.BULK_OPERATION_CREATE)
    fun submit(
        @Body @Valid req: BulkCaseReassignRequest,
        authentication: Authentication?
    ): BulkOperationResponse {
        val requestingUser = authentication?.name?.let { email ->
            userRepository.findByEmail(email).orElse(null)
        }
        val job = bulkOperationService.submitReassignJob(req, requestingUser)
        return BulkOperationResponse.from(bulkOperationService.get(job.id!!) ?: job)
    }

    @Operation(summary = "Get bulk reassignment job status", description = "Retrieves current execution progress, total count, processed count, and error summary for a bulk job")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Job status found"),
        ApiResponse(responseCode = "404", description = "Job not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing BULK_OPERATION_GET permission")
    )
    @Get("/{jobId}")
    @NeedsPermission(Permission.BULK_OPERATION_GET)
    fun get(@PathVariable jobId: Long): BulkOperationResponse {
        val job = bulkOperationService.get(jobId)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "Bulk operation job not found: $jobId")
        return BulkOperationResponse.from(job)
    }
}
