package de.legalhub.adapters.output.repository

import de.legalhub.model.Action
import io.micronaut.data.annotation.Join
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.MYSQL)
interface ActionRepository : CrudRepository<Action, Long> {

    @Join(value = "legalCase", type = Join.Type.LEFT_FETCH)
    @Join(value = "legalCase.partnerAgency", type = Join.Type.LEFT_FETCH)
    @Join(value = "assignee", type = Join.Type.LEFT_FETCH)
    @Join(value = "createdBy", type = Join.Type.LEFT_FETCH)
    override fun findById(id: Long): Optional<Action>

    fun findByLegalCaseId(legalCaseId: Long): List<Action>
}
