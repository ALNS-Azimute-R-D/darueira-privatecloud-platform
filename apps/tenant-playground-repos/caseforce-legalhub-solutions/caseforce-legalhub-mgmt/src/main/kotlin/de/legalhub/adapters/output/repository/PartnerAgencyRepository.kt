package de.legalhub.adapters.output.repository

import de.legalhub.model.PartnerAgency
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository

import java.util.Optional

@JdbcRepository(dialect = Dialect.POSTGRES)
interface PartnerAgencyRepository : CrudRepository<PartnerAgency, Long> {
    fun findByAlias(alias: String): Optional<PartnerAgency>
    fun findByAliasAndDeletedAtIsNull(alias: String): Optional<PartnerAgency>
    fun existsByAlias(alias: String): Boolean
    fun findByDeletedAtIsNull(): List<PartnerAgency>
}
