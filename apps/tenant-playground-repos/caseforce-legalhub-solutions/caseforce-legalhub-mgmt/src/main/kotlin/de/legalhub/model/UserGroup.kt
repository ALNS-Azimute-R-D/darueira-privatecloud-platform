package de.legalhub.model

import io.micronaut.serde.annotation.Serdeable
import jakarta.persistence.*

@Serdeable
@Entity
@Table(name = "tb_user_group")
class UserGroup {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @ManyToOne
    @JoinColumn(name = "user_id", nullable = false)
    var user: User? = null

    @ManyToOne
    @JoinColumn(name = "group_id", nullable = false)
    var group: Group? = null

}
