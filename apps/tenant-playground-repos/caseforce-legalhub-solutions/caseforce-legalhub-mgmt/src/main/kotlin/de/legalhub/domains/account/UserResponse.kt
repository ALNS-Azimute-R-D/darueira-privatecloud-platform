package de.legalhub.domains.account

import de.legalhub.model.User
import de.legalhub.model.UserRole
import io.micronaut.serde.annotation.Serdeable
import io.swagger.v3.oas.annotations.media.Schema
import java.time.Instant

@Serdeable
@Schema(description = "User representation")
data class UserResponse(
    @field:Schema(description = "User ID", example = "1")
    val id: Long? = null,

    @field:Schema(description = "Email address", example = "john.doe@caseforce.de")
    val email: String = "",

    @field:Schema(description = "First name", example = "John")
    val firstname: String? = null,

    @field:Schema(description = "Last name", example = "Doe")
    val lastname: String? = null,

    @field:Schema(description = "Account enabled status", example = "true")
    val enabled: Boolean = true,

    @field:Schema(description = "Roles assigned to user", example = "[\"CASEFORCE\"]")
    val roles: List<String> = emptyList(),

    @field:Schema(description = "Creation timestamp")
    val createdAt: Instant? = null,

    @field:Schema(description = "Last update timestamp")
    val updatedAt: Instant? = null
) {
    companion object {
        fun from(user: User, roles: List<UserRole> = emptyList()): UserResponse {
            return UserResponse(
                id = user.id,
                email = user.email,
                firstname = user.firstname,
                lastname = user.lastname,
                enabled = user.enabled,
                roles = roles.map { it.role.name },
                createdAt = user.createdAt,
                updatedAt = user.updatedAt
            )
        }
    }
}
