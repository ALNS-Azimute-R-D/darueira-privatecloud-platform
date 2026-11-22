package de.legalhub.domains.account

import de.legalhub.domains.auth.NeedsPermission
import de.legalhub.domains.auth.Permission
import de.legalhub.model.ListResult
import de.legalhub.model.UserRole
import io.micronaut.http.HttpResponse
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

@Tag(name = "Users", description = "Management and lifecycle of users, credentials, and roles")
@SecurityRequirement(name = "BearerAuth")
@Controller("/users")
@Secured(SecurityRule.IS_AUTHENTICATED)
@ExecuteOn(TaskExecutors.BLOCKING)
open class UserController(
    private val userService: UserService,
    private val groupService: GroupService,
) {

    @Operation(summary = "Get user by ID", description = "Retrieves user details and roles by user ID")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "User details returned"),
        ApiResponse(responseCode = "404", description = "User not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing USER_GET permission")
    )
    @Get("/{id}")
    @NeedsPermission(Permission.USER_GET)
    fun get(@PathVariable id: Long): UserResponse {
        return userService.get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "User not found")
    }

    @Operation(summary = "List users", description = "Lists all active users")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of users returned"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing USER_LIST permission")
    )
    @Get
    @NeedsPermission(Permission.USER_LIST)
    fun list(): ListResult<UserResponse> {
        val users = userService.list()
        return ListResult(
            list = users,
            totalCount = users.size.toLong()
        )
    }

    @Operation(summary = "Create user", description = "Creates a new user with initial credentials and roles")
    @ApiResponses(
        ApiResponse(responseCode = "201", description = "User created successfully"),
        ApiResponse(responseCode = "400", description = "Invalid payload"),
        ApiResponse(responseCode = "409", description = "User with email already exists"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing USER_CREATE permission")
    )
    @Post
    @Status(HttpStatus.CREATED)
    @NeedsPermission(Permission.USER_CREATE)
    fun create(@Body @Valid cmd: UserCommands.Create): UserResponse {
        return userService.create(cmd)
    }

    @Operation(summary = "Update user", description = "Updates profile, status, password, or roles of an existing user")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "User updated successfully"),
        ApiResponse(responseCode = "404", description = "User not found"),
        ApiResponse(responseCode = "409", description = "Email already in use by another user"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing USER_UPDATE permission")
    )
    @Put("/{id}")
    @NeedsPermission(Permission.USER_UPDATE)
    fun update(@PathVariable id: Long, @Body @Valid cmd: UserCommands.Update): UserResponse {
        return userService.update(id, cmd)
    }

    @Operation(summary = "Delete user", description = "Soft deletes a user and revokes group memberships")
    @ApiResponses(
        ApiResponse(responseCode = "204", description = "User deleted successfully"),
        ApiResponse(responseCode = "404", description = "User not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing USER_DELETE permission")
    )
    @Delete("/{id}")
    @Status(HttpStatus.NO_CONTENT)
    @NeedsPermission(Permission.USER_DELETE)
    fun delete(@PathVariable id: Long): HttpResponse<Void> {
        userService.delete(id)
        return HttpResponse.noContent()
    }

    @Operation(summary = "List groups of a user", description = "Retrieves all permission groups the user belongs to")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of user's groups returned"),
        ApiResponse(responseCode = "404", description = "User not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_MEMBERSHIP_LIST permission")
    )
    @Get("/{userId}/groups")
    @NeedsPermission(Permission.GROUP_MEMBERSHIP_LIST)
    fun getUserGroups(@PathVariable userId: Long): ListResult<GroupResponse> {
        val groups = groupService.listUserGroups(userId)
        return ListResult(
            list = groups,
            totalCount = groups.size.toLong()
        )
    }
}
