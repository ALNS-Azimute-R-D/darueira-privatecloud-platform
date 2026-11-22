package de.legalhub.model

import io.micronaut.data.annotation.DateCreated
import io.micronaut.data.annotation.TypeDef
import io.micronaut.data.model.DataType
import io.micronaut.serde.annotation.Serdeable
import jakarta.persistence.*
import java.time.Instant

@Serdeable
@Entity
@Table(name = "tb_user_role")
class UserRole {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @Column(name = "ds_role", nullable = false)
    @TypeDef(type = DataType.STRING)
    var role: Role = Role.CASEFORCE

    @ManyToOne
    @JoinColumn(name = "user_id", nullable = false)
    var user: User? = null

    @Column(name = "ts_date_created")
    @DateCreated
    var createdAt: Instant? = null

    enum class Role {
        ROOT,
        LEGAL_HERO,
        CASEFORCE;

        companion object {
            const val ROLE_ROOT = "ROOT"
            const val ROLE_LEGAL_HERO = "LEGAL_HERO"
            const val ROLE_CASEFORCE = "CASEFORCE"
        }
    }
}
