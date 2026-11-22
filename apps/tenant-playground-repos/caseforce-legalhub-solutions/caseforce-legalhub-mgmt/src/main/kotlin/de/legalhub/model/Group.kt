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
@Table(name = "tb_permission_group")
class Group {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_name", nullable = false)
    var name: String = ""

    @Column(name = "ts_date_created")
    @DateCreated
    var createdAt: Instant? = null

    @Column(name = "ts_date_updated")
    @DateUpdated
    var updatedAt: Instant? = null


    @Column(name = "js_permissions", nullable = false)
    @TypeDef(type = DataType.JSON)
    var permissions: List<String> = emptyList()

}
