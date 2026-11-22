package de.legalhub.domains.action

import de.legalhub.domains.auth.NeedsPermission
import de.legalhub.domains.auth.Permission
import de.legalhub.model.ListResult
import de.legalhub.model.UserRole
import de.legalhub.adapters.output.repository.UserRepository
import io.micronaut.http.HttpStatus
import io.micronaut.http.annotation.Body
import io.micronaut.http.annotation.Controller
import io.micronaut.http.annotation.Get
import io.micronaut.http.annotation.PathVariable
import io.micronaut.http.annotation.Post
import io.micronaut.http.annotation.Put
import io.micronaut.http.annotation.QueryValue
import io.micronaut.http.exceptions.HttpStatusException
import io.micronaut.scheduling.TaskExecutors
import io.micronaut.scheduling.annotation.ExecuteOn
import io.micronaut.security.annotation.Secured
import io.micronaut.security.rules.SecurityRule
import io.micronaut.security.utils.SecurityService
import io.swagger.v3.oas.annotations.Operation
import io.swagger.v3.oas.annotations.responses.ApiResponse
import io.swagger.v3.oas.annotations.responses.ApiResponses
import io.swagger.v3.oas.annotations.security.SecurityRequirement
import io.swagger.v3.oas.annotations.tags.Tag

@Tag(name = "Actions", description = "Management of tasks and actions associated with legal cases")
@SecurityRequirement(name = "BearerAuth")
@Controller("/actions")
@Secured(SecurityRule.IS_AUTHENTICATED)
@ExecuteOn(TaskExecutors.BLOCKING)
open class ActionController(
    private val actionService: ActionService,
    private val securityService: SecurityService,
    private val userRepository: UserRepository,
) {

    @Operation(summary = "Get action by ID", description = "Retrieves details of a specific case action")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Action found and returned"),
        ApiResponse(responseCode = "404", description = "Action not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing ACTION_GET permission")
    )
    @Get("/{id}")
    @NeedsPermission(Permission.ACTION_GET)
    fun get(@PathVariable id: Long): ActionResponse {
        val action = actionService.get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "Action not found")
        return ActionResponse.from(action)
    }

    @Operation(summary = "List actions by case", description = "Lists all actions associated with a specific legal case ID")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of actions returned"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing ACTION_LIST permission")
    )
    @Get
    @NeedsPermission(Permission.ACTION_LIST)
    fun listByCase(@QueryValue legalCaseId: Long): ListResult<ActionResponse> {
        val actions = actionService.listByLegalCase(legalCaseId)
        return ListResult(
            list = actions.map { ActionResponse.from(it) },
            totalCount = actions.size.toLong()
        )
    }

    @Operation(summary = "Create an action", description = "Creates a new action under a case and emits an entity event")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Action created successfully"),
        ApiResponse(responseCode = "400", description = "Invalid payload"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing ACTION_CREATE permission")
    )
    @Post
    @NeedsPermission(Permission.ACTION_CREATE)
    fun create(@Body cmd: ActionCommands.Create): ActionResponse {
        val email = securityService.authentication.orElseThrow().name
        val user = userRepository.findByEmail(email).orElseThrow()
        val action = actionService.create(cmd, user.id!!)
        return ActionResponse.from(action)
    }

    @Operation(summary = "Update an action", description = "Updates an existing action and emits an entity event")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Action updated successfully"),
        ApiResponse(responseCode = "404", description = "Action not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing ACTION_UPDATE permission")
    )
    @Put("/{id}")
    @NeedsPermission(Permission.ACTION_UPDATE)
    fun update(@PathVariable id: Long, @Body cmd: ActionCommands.Update): ActionResponse {
        val action = actionService.update(id, cmd)
        return ActionResponse.from(action)
    }
}

