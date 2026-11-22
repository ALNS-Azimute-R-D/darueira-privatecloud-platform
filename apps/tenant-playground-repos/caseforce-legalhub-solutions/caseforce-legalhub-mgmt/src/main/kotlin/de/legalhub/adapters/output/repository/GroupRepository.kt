package de.legalhub.adapters.output.repository

import de.legalhub.model.Group
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.POSTGRES)
interface GroupRepository : CrudRepository<Group, Long> {

    fun findByName(name: String): Optional<Group>

    fun existsByName(name: String): Boolean
}
