package de.legalhub.adapters.output.repository

import de.legalhub.model.User
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.POSTGRES)
interface UserRepository : CrudRepository<User, Long> {

    fun findByEmail(email: String): Optional<User>

    fun existsByEmail(email: String): Boolean

    fun findByDeletedAtIsNull(): List<User>

    fun findByIdAndDeletedAtIsNull(id: Long): Optional<User>
}
