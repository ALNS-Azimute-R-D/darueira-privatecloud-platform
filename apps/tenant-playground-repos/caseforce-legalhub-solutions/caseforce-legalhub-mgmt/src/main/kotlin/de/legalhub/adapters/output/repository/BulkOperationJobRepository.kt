package de.legalhub.adapters.output.repository

import de.legalhub.model.BulkOperationJob
import io.micronaut.data.annotation.Join
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.POSTGRES)
interface BulkOperationJobRepository : CrudRepository<BulkOperationJob, Long> {

    @Join(value = "requestedBy", type = Join.Type.LEFT_FETCH)
    @Join(value = "targetLawyer", type = Join.Type.LEFT_FETCH)
    override fun findById(id: Long): Optional<BulkOperationJob>

    @Join(value = "requestedBy", type = Join.Type.LEFT_FETCH)
    @Join(value = "targetLawyer", type = Join.Type.LEFT_FETCH)
    fun findByStatus(status: BulkOperationJob.Status): List<BulkOperationJob>
}
