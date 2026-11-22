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
@Table(name = "tb_partner_agency")
class PartnerAgency {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_alias", nullable = false)
    var alias: String = ""

    @Column(name = "ds_name", nullable = false)
    var name: String = ""

    @Column(name = "ds_email")
    var email: String? = null

    @Column(name = "en_status", nullable = false)
    @TypeDef(type = DataType.STRING)
    var status: Status = Status.ACTIVE

    @DateCreated
    @Column(name = "ts_date_created")
    var createdAt: Instant? = null

    @DateUpdated
    @Column(name = "ts_date_updated")
    var updatedAt: Instant? = null

    @Column(name = "ts_date_deleted")
    var deletedAt: Instant? = null

    enum class Status {
        ACTIVE,
        INACTIVE,
        BLOCKED
    }
}
