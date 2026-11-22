package de.legalhub.model

import io.micronaut.data.annotation.DateCreated
import io.micronaut.data.annotation.DateUpdated
import io.micronaut.data.annotation.TypeDef
import io.micronaut.data.model.DataType
import io.micronaut.serde.annotation.Serdeable
import jakarta.persistence.*
import java.time.Instant

@Serdeable
@Entity
@Table(name = "tb_bulk_operation_job")
class BulkOperationJob {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_job_type", nullable = false)
    var jobType: String = "CASE_REASSIGNMENT"

    @Column(name = "en_status", nullable = false)
    @TypeDef(type = DataType.STRING)
    var status: Status = Status.PENDING

    @Column(name = "nr_total_count", nullable = false)
    var totalCount: Int = 0

    @Column(name = "nr_processed_count", nullable = false)
    var processedCount: Int = 0

    @Column(name = "nr_success_count", nullable = false)
    var successCount: Int = 0

    @Column(name = "nr_failed_count", nullable = false)
    var failedCount: Int = 0

    @ManyToOne
    @JoinColumn(name = "requested_by_id", nullable = false)
    var requestedBy: User? = null

    @ManyToOne
    @JoinColumn(name = "target_lawyer_id", nullable = false)
    var targetLawyer: User? = null

    @DateCreated
    @Column(name = "ts_date_created")
    var createdAt: Instant? = null

    @DateUpdated
    @Column(name = "ts_date_updated")
    var updatedAt: Instant? = null

    @Column(name = "js_filter_criteria", nullable = false)
    @TypeDef(type = DataType.JSON)
    var filterCriteria: String = "{}"

    @Column(name = "js_error_summary")
    @TypeDef(type = DataType.JSON)
    var errorSummary: String? = null

    enum class Status {
        PENDING,
        IN_PROGRESS,
        COMPLETED,
        FAILED
    }
}
