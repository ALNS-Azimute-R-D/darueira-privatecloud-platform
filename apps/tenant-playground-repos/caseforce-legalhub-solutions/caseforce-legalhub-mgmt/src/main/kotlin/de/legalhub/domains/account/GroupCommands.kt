package de.legalhub.domains.account

import io.micronaut.serde.annotation.Serdeable
import io.swagger.v3.oas.annotations.media.Schema
import jakarta.validation.constraints.NotBlank

object GroupCommands {

    @Serdeable
    @Schema(description = "Payload to create a new permission Group")
    data class Create(
        @field:NotBlank(message = "Group name is required")
        @field:Schema(description = "Unique group name", example = "CaseManagers", required = true)
        var name: String? = null,

        @field:Schema(description = "List of permissions assigned to this group", example = "[\"CASE_CREATE\", \"CASE_GET\", \"CASE_UPDATE\", \"CASE_LIST\"]")
        var permissions: List<String> = emptyList()
    )

    @Serdeable
    @Schema(description = "Payload to update an existing permission Group")
    data class Update(
        @field:Schema(description = "Updated group name", example = "SeniorCaseManagers")
        var name: String? = null,

        @field:Schema(description = "Updated list of permissions", example = "[\"CASE_CREATE\", \"CASE_GET\", \"CASE_UPDATE\", \"CASE_LIST\", \"CASE_DELETE\"]")
        var permissions: List<String>? = null
    )

    @Serdeable
    @Schema(description = "Payload to add a user member to a Group")
    data class AddMember(
        @field:Schema(description = "User ID to add to group", example = "1", required = true)
        var userId: Long? = null
    )
}
