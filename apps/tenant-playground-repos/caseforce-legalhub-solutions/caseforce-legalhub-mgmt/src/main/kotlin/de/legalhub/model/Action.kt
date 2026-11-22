package de.legalhub.model

import io.micronaut.data.annotation.DateCreated
import io.micronaut.data.annotation.DateUpdated
import io.micronaut.data.annotation.TypeDef
import io.micronaut.data.model.DataType
import io.micronaut.serde.annotation.Serdeable
import jakarta.persistence.Column
import jakarta.persistence.Entity
import jakarta.persistence.GeneratedValue
import jakarta.persistence.GenerationType
import jakarta.persistence.Id
import jakarta.persistence.JoinColumn
import jakarta.persistence.ManyToOne
import jakarta.persistence.Table
import java.time.Instant
import java.time.LocalDate

@Serdeable
@Entity
@Table(name = "tb_action")
class Action {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_name", nullable = false)
    var name: String = ""

    @Column(name = "is_task")
    var isTask: Boolean = false

    @Column(name = "en_status")
    @TypeDef(type = DataType.STRING)
    var status: ActionStatus = ActionStatus.OPEN

    @ManyToOne
    @Column(name = "legal_case_id")
    var legalCase: LegalCase? = null

    @ManyToOne
    @JoinColumn(name = "assignee_id")
    var assignee: User? = null

    @ManyToOne
    @JoinColumn(name = "created_by_id")
    var createdBy: User? = null


    @Column(name = "dt_due_date")
    var dueDate: LocalDate? = null

    @Column(name = "ts_date_created")
    @DateCreated
    var createdAt: Instant? = null

    @Column(name = "ts_date_updated")
    @DateUpdated
    var updatedAt: Instant? = null

    @Column(name = "ts_date_deleted")
    var deletedAt: Instant? = null

    @Column(name = "tx_notes")
    var notes: String? = null

}

enum class ActionStatus {
    OPEN,
    IN_PROGRESS,
    COMPLETED,
    CANCELLED
}
