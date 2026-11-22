package de.legalhub.adapters.output.repository

import de.legalhub.model.LegalCase
import io.micronaut.data.annotation.Join
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.POSTGRES)
interface LegalCaseRepository : CrudRepository<LegalCase, Long> {

    @Join(value = "lawyer", type = Join.Type.LEFT_FETCH)
    @Join(value = "assignee", type = Join.Type.LEFT_FETCH)
    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    override fun findById(id: Long): Optional<LegalCase>

    @Join(value = "lawyer", type = Join.Type.LEFT_FETCH)
    @Join(value = "assignee", type = Join.Type.LEFT_FETCH)
    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    fun findByCaseNumber(caseNumber: String): Optional<LegalCase>

    fun existsByCaseNumber(caseNumber: String): Boolean

    @Join(value = "lawyer", type = Join.Type.LEFT_FETCH)
    @Join(value = "assignee", type = Join.Type.LEFT_FETCH)
    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    fun findByPartnerAgencyId(partnerAgencyId: Long): List<LegalCase>

    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    fun findByDeletedAtIsNull(): List<LegalCase>
}
