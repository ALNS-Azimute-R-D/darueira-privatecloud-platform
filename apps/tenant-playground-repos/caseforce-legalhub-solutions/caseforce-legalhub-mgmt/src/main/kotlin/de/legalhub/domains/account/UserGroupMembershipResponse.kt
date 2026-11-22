package de.legalhub.domains.account

import de.legalhub.model.Group
import de.legalhub.model.User
import de.legalhub.model.UserGroup
import io.micronaut.serde.annotation.Serdeable
import io.swagger.v3.oas.annotations.media.Schema

@Serdeable
@Schema(description = "Group membership association between a User and a Group")
data class UserGroupMembershipResponse(
    @field:Schema(description = "Membership record ID", example = "10")
    val id: Long? = null,

    @field:Schema(description = "User ID", example = "1")
    val userId: Long? = null,

    @field:Schema(description = "User email", example = "john.doe@caseforce.de")
    val userEmail: String? = null,

    @field:Schema(description = "User full name", example = "John Doe")
    val userFullName: String? = null,

    @field:Schema(description = "Group ID", example = "2")
    val groupId: Long? = null,

    @field:Schema(description = "Group name", example = "CaseManagers")
    val groupName: String? = null
) {
    companion object {
        fun from(userGroup: UserGroup, user: User? = null, group: Group? = null): UserGroupMembershipResponse {
            val u = user ?: userGroup.user
            val g = group ?: userGroup.group
            val fullName = listOfNotNull(u?.firstname, u?.lastname).joinToString(" ").ifBlank { null }
            return UserGroupMembershipResponse(
                id = userGroup.id,
                userId = u?.id,
                userEmail = u?.email,
                userFullName = fullName,
                groupId = g?.id,
                groupName = g?.name
            )
        }
    }
}
