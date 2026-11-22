package de.legalhub.model

import com.fasterxml.jackson.annotation.JsonIgnore
import io.micronaut.data.annotation.DateCreated
import io.micronaut.data.annotation.DateUpdated
import io.micronaut.serde.annotation.Serdeable
import jakarta.persistence.*
import java.time.Instant

@Serdeable
@Entity
@Table(name = "tb_user")
class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_email", nullable = false, unique = true)
    var email: String = ""

    @Column(name = "ds_firstname")
    var firstname: String? = null

    @Column(name = "ds_lastname")
    var lastname: String? = null

    @Column(name = "ds_password", nullable = false)
    @JsonIgnore
    var password: String? = null

    @Column(name = "is_enabled", nullable = false)
    var enabled: Boolean = true

    @DateCreated
    @Column(name = "ts_date_created")
    var createdAt: Instant? = null

    @DateUpdated
    @Column(name = "ts_date_updated")
    var updatedAt: Instant? = null

    @Column(name = "ts_date_deleted")
    var deletedAt: Instant? = null

}
