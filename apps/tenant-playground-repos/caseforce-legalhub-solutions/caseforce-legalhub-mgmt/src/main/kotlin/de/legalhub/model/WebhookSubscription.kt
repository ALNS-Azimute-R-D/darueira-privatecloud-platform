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
@Table(name = "tb_webhook_subscription")
class WebhookSubscription {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_target_url", nullable = false)
    var targetUrl: String = ""

    @Column(name = "ds_secret", nullable = false)
    var secret: String = ""

    @Column(name = "en_status", nullable = false)
    @TypeDef(type = DataType.STRING)
    var status: Status = Status.ACTIVE

    @ManyToOne
    @JoinColumn(name = "partner_agency_id", nullable = false)
    var partnerAgency: PartnerAgency? = null

    @DateCreated
    @Column(name = "ts_date_created")
    var createdAt: Instant? = null

    @DateUpdated
    @Column(name = "ts_date_updated")
    var updatedAt: Instant? = null

    @Column(name = "ts_date_deleted")
    var deletedAt: Instant? = null

    @Column(name = "js_event_types", nullable = false)
    @TypeDef(type = DataType.JSON)
    var eventTypes: List<String> = emptyList()


    enum class Status {
        ACTIVE,
        INACTIVE,
        SUSPENDED
    }
}
