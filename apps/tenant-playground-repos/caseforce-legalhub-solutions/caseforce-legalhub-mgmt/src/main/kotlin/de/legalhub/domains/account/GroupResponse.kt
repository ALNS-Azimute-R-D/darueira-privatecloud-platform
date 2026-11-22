package de.legalhub.domains.account

import de.legalhub.model.Group
import io.micronaut.serde.annotation.Serdeable
import io.swagger.v3.oas.annotations.media.Schema
import java.time.Instant

@Serdeable
@Schema(description = "Permission group representation")
data class GroupResponse(
    @field:Schema(description = "Group ID", example = "1")
    val id: Long? = null,

    @field:Schema(description = "Group name", example = "CaseManagers")
    val name: String = "",

    @field:Schema(description = "List of permissions assigned to this group", example = "[\"CASE_CREATE\", \"CASE_GET\"]")
    val permissions: List<String> = emptyList(),

    @field:Schema(description = "Number of user members in this group", example = "3")
    val memberCount: Long? = null,

    @field:Schema(description = "Creation timestamp")
    val createdAt: Instant? = null,

    @field:Schema(description = "Last update timestamp")
    val updatedAt: Instant? = null
) {
    companion object {
        fun from(group: Group, memberCount: Long? = null): GroupResponse {
            return GroupResponse(
                id = group.id,
                name = group.name,
                permissions = group.permissions,
                memberCount = memberCount,
                createdAt = group.createdAt,
                updatedAt = group.updatedAt
            )
        }
    }
}
