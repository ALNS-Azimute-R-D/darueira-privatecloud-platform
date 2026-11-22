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

@Tag(name = "Permission Groups", description = "Management of permission groups and user group memberships")
@SecurityRequirement(name = "BearerAuth")
@Controller("/groups")
@Secured(SecurityRule.IS_AUTHENTICATED)
@ExecuteOn(TaskExecutors.BLOCKING)
open class GroupController(
    private val groupService: GroupService,
) {

    @Operation(summary = "Get group by ID", description = "Retrieves details and member count of a permission group")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Group details returned"),
        ApiResponse(responseCode = "404", description = "Group not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_GET permission")
    )
    @Get("/{id}")
    @NeedsPermission(Permission.GROUP_GET)
    fun get(@PathVariable id: Long): GroupResponse {
        return groupService.get(id)
            ?: throw HttpStatusException(HttpStatus.NOT_FOUND, "Group not found")
    }

    @Operation(summary = "List groups", description = "Lists all permission groups")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of groups returned"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_LIST permission")
    )
    @Get
    @NeedsPermission(Permission.GROUP_LIST)
    fun list(): ListResult<GroupResponse> {
        val groups = groupService.list()
        return ListResult(
            list = groups,
            totalCount = groups.size.toLong()
        )
    }

    @Operation(summary = "Create group", description = "Creates a new permission group")
    @ApiResponses(
        ApiResponse(responseCode = "201", description = "Group created successfully"),
        ApiResponse(responseCode = "400", description = "Invalid payload"),
        ApiResponse(responseCode = "409", description = "Group with name already exists"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_CREATE permission")
    )
    @Post
    @Status(HttpStatus.CREATED)
    @NeedsPermission(Permission.GROUP_CREATE)
    fun create(@Body @Valid cmd: GroupCommands.Create): GroupResponse {
        return groupService.create(cmd)
    }

    @Operation(summary = "Update group", description = "Updates group name or permissions")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "Group updated successfully"),
        ApiResponse(responseCode = "404", description = "Group not found"),
        ApiResponse(responseCode = "409", description = "Group name already in use"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_UPDATE permission")
    )
    @Put("/{id}")
    @NeedsPermission(Permission.GROUP_UPDATE)
    fun update(@PathVariable id: Long, @Body @Valid cmd: GroupCommands.Update): GroupResponse {
        return groupService.update(id, cmd)
    }

    @Operation(summary = "Delete group", description = "Deletes a permission group and all its memberships")
    @ApiResponses(
        ApiResponse(responseCode = "204", description = "Group deleted successfully"),
        ApiResponse(responseCode = "404", description = "Group not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_DELETE permission")
    )
    @Delete("/{id}")
    @Status(HttpStatus.NO_CONTENT)
    @NeedsPermission(Permission.GROUP_DELETE)
    fun delete(@PathVariable id: Long): HttpResponse<Void> {
        groupService.delete(id)
        return HttpResponse.noContent()
    }

    @Operation(summary = "Add member to group by path", description = "Adds a user to the specified permission group")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "User added to group successfully"),
        ApiResponse(responseCode = "404", description = "Group or user not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_MEMBERSHIP_ADD permission")
    )
    @Post("/{groupId}/members/{userId}")
    @NeedsPermission(Permission.GROUP_MEMBERSHIP_ADD)
    fun addMember(@PathVariable groupId: Long, @PathVariable userId: Long): UserGroupMembershipResponse {
        return groupService.addMember(groupId, userId)
    }

    @Operation(summary = "Add member to group by body", description = "Adds a user specified in request body to group")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "User added to group successfully"),
        ApiResponse(responseCode = "400", description = "User ID missing in payload"),
        ApiResponse(responseCode = "404", description = "Group or user not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_MEMBERSHIP_ADD permission")
    )
    @Post("/{groupId}/members")
    @NeedsPermission(Permission.GROUP_MEMBERSHIP_ADD)
    fun addMemberWithBody(@PathVariable groupId: Long, @Body cmd: GroupCommands.AddMember): UserGroupMembershipResponse {
        val userId = cmd.userId ?: throw HttpStatusException(HttpStatus.BAD_REQUEST, "userId is required")
        return groupService.addMember(groupId, userId)
    }

    @Operation(summary = "Remove member from group", description = "Removes a user from the permission group")
    @ApiResponses(
        ApiResponse(responseCode = "204", description = "User removed from group successfully"),
        ApiResponse(responseCode = "404", description = "Group or user not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_MEMBERSHIP_REMOVE permission")
    )
    @Delete("/{groupId}/members/{userId}")
    @Status(HttpStatus.NO_CONTENT)
    @NeedsPermission(Permission.GROUP_MEMBERSHIP_REMOVE)
    fun removeMember(@PathVariable groupId: Long, @PathVariable userId: Long): HttpResponse<Void> {
        groupService.removeMember(groupId, userId)
        return HttpResponse.noContent()
    }

    @Operation(summary = "List members of a group", description = "Lists all users belonging to the specified group")
    @ApiResponses(
        ApiResponse(responseCode = "200", description = "List of member users returned"),
        ApiResponse(responseCode = "404", description = "Group not found"),
        ApiResponse(responseCode = "401", description = "Unauthorized"),
        ApiResponse(responseCode = "403", description = "Forbidden - missing GROUP_MEMBERSHIP_LIST permission")
    )
    @Get("/{groupId}/members")
    @NeedsPermission(Permission.GROUP_MEMBERSHIP_LIST)
    fun listMembers(@PathVariable groupId: Long): ListResult<UserResponse> {
        val members = groupService.listGroupMembers(groupId)
        return ListResult(
            list = members,
            totalCount = members.size.toLong()
        )
    }
}
