package de.legalhub.adapters.output.repository

import de.legalhub.model.WebhookSubscription
import io.micronaut.data.annotation.Join
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.MYSQL)
interface WebhookSubscriptionRepository : CrudRepository<WebhookSubscription, Long> {

    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    override fun findById(id: Long): Optional<WebhookSubscription>

    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    fun findByPartnerAgencyIdAndDeletedAtIsNull(partnerAgencyId: Long): List<WebhookSubscription>

    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    fun findByPartnerAgencyIdAndStatusAndDeletedAtIsNull(
        partnerAgencyId: Long,
        status: WebhookSubscription.Status
    ): List<WebhookSubscription>

    @Join(value = "partnerAgency", type = Join.Type.LEFT_FETCH)
    fun findByDeletedAtIsNull(): List<WebhookSubscription>
}
