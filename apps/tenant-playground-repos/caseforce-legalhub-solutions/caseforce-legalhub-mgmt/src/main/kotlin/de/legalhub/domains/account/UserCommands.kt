package de.legalhub.domains.account

import de.legalhub.model.UserRole
import io.micronaut.serde.annotation.Serdeable
import io.swagger.v3.oas.annotations.media.Schema
import jakarta.validation.constraints.Email
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size

object UserCommands {

    @Serdeable
    @Schema(description = "Payload to create a new User")
    data class Create(
        @field:NotBlank(message = "Email is required")
        @field:Email(message = "Email must be a valid email address")
        @field:Schema(description = "Unique email address", example = "john.doe@caseforce.de", required = true)
        var email: String? = null,

        @field:Schema(description = "User's first name", example = "John")
        var firstname: String? = null,

        @field:Schema(description = "User's last name", example = "Doe")
        var lastname: String? = null,

        @field:NotBlank(message = "Password is required")
        @field:Size(min = 6, message = "Password must be at least 6 characters")
        @field:Schema(description = "User's password", example = "SecurePass123!", required = true)
        var password: String? = null,

        @field:Schema(description = "Whether the user account is enabled", example = "true", defaultValue = "true")
        var enabled: Boolean = true,

        @field:Schema(description = "List of user roles", example = "[\"CASEFORCE\"]")
        var roles: List<UserRole.Role> = listOf(UserRole.Role.CASEFORCE)
    )

    @Serdeable
    @Schema(description = "Payload to update an existing User")
    data class Update(
        @field:Email(message = "Email must be a valid email address")
        @field:Schema(description = "Updated email address", example = "john.updated@caseforce.de")
        var email: String? = null,

        @field:Schema(description = "Updated first name", example = "Johnny")
        var firstname: String? = null,

        @field:Schema(description = "Updated last name", example = "Doe")
        var lastname: String? = null,

        @field:Size(min = 6, message = "Password must be at least 6 characters")
        @field:Schema(description = "New password (leave null/blank to keep current)", example = "NewSecurePass123!")
        var password: String? = null,

        @field:Schema(description = "Whether the user account is enabled", example = "true")
        var enabled: Boolean? = null,

        @field:Schema(description = "Updated list of user roles", example = "[\"LEGAL_HERO\", \"CASEFORCE\"]")
        var roles: List<UserRole.Role>? = null
    )
}
