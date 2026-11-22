package de.legalhub.domains.action

import de.legalhub.model.Action
import io.micronaut.serde.annotation.Serdeable
import java.time.Instant
import java.time.LocalDate

@Serdeable
data class ActionResponse(
    val id: Long,
    val legalCaseId: Long?,
    val name: String,
    val isTask: Boolean,
    val status: String,
    val assigneeId: Long?,
    val createdById: Long?,
    val dueDate: LocalDate?,
    val notes: String?,
    val dateCreated: Instant?,
) {
    companion object {
        fun from(action: Action) = ActionResponse(
            id = action.id!!,
            legalCaseId = action.legalCase?.id,
            name = action.name,
            isTask = action.isTask,
            status = action.status.name,
            assigneeId = action.assignee?.id,
            createdById = action.createdBy?.id,
            dueDate = action.dueDate,
            notes = action.notes,
            dateCreated = action.createdAt,
        )
    }
}
