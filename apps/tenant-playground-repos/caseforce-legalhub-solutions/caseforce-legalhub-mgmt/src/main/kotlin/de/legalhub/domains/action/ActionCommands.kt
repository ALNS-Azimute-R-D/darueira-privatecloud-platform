package de.legalhub.domains.action

import io.micronaut.serde.annotation.Serdeable
import java.time.LocalDate

object ActionCommands {

    @Serdeable
    data class Create(
        var legalCaseId: Long = 0,
        var name: String = "",
        var isTask: Boolean = false,
        var assigneeId: Long? = null,
        var dueDate: LocalDate? = null,
        var notes: String? = null,
    )

    @Serdeable
    data class Update(
        var name: String? = null,
        var status: String? = null,
        var assigneeId: Long? = null,
        var dueDate: LocalDate? = null,
        var notes: String? = null,
    )
}
