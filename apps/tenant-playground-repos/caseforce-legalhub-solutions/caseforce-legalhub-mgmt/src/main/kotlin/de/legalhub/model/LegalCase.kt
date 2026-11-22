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

@Serdeable
@Entity
@Table(name = "tb_legal_case")
class LegalCase {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_case_number", nullable = false, unique = true)
    var caseNumber: String? = null

    @Column(name = "ds_legal_field")
    var legalField: String? = null

    @Column(name = "en_status", nullable = false)
    @TypeDef(type = DataType.STRING)
    var status: CaseStatus = CaseStatus.OPEN

    @ManyToOne
    @JoinColumn(name = "lawyer_id")
    var lawyer: User? = null

    @ManyToOne
    @JoinColumn(name = "assignee_id")
    var assignee: User? = null

    @ManyToOne
    @JoinColumn(name = "partner_agency_id")
    var partnerAgency: PartnerAgency? = null

    @DateCreated
    @Column(name = "ts_date_created")
    var createdAt: Instant? = null

    @DateUpdated
    @Column(name = "ts_date_updated")
    var updatedAt: Instant? = null

    @Column(name = "ts_date_deleted")
    var deletedAt: Instant? = null

    @Column(name = "tx_summary")
    var summary: String? = null

}

enum class CaseStatus {
    OPEN,
    IN_PROGRESS,
    CLOSED,
    ARCHIVED
}
