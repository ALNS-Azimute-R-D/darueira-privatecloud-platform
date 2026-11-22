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
@Table(name = "tb_webhook_delivery")
class WebhookDelivery {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_event_type", nullable = false)
    var eventType: String = ""

    @Column(name = "ds_entity_type", nullable = false)
    var entityType: String = ""

    @Column(name = "nr_entity_id", nullable = false)
    var entityId: Long = 0

    @Column(name = "en_status", nullable = false)
    @TypeDef(type = DataType.STRING)
    var status: Status = Status.PENDING

    @Column(name = "nr_attempt_count", nullable = false)
    var attemptCount: Int = 0

    @Column(name = "nr_response_status_code")
    var responseStatusCode: Int? = null


    @ManyToOne
    @JoinColumn(name = "subscription_id", nullable = false)
    var subscription: WebhookSubscription? = null


    @Column(name = "ts_last_attempt_at")
    var lastAttemptAt: Instant? = null

    @DateCreated
    @Column(name = "ts_date_created")
    var createdAt: Instant? = null

    @DateUpdated
    @Column(name = "ts_date_updated")
    var updatedAt: Instant? = null


    @Column(name = "js_payload", nullable = false)
    @TypeDef(type = DataType.JSON)
    var payload: String = "{}"

    @Column(name = "tx_response_body")
    var responseBody: String? = null

    @Column(name = "tx_error_message")
    var errorMessage: String? = null


    enum class Status {
        PENDING,
        SUCCESS,
        FAILED
    }
}
