package de.legalhub.adapters.output.repository

import de.legalhub.model.WebhookDelivery
import io.micronaut.data.annotation.Join
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.MYSQL)
interface WebhookDeliveryRepository : CrudRepository<WebhookDelivery, Long> {

    @Join(value = "subscription", type = Join.Type.LEFT_FETCH)
    override fun findById(id: Long): Optional<WebhookDelivery>

    @Join(value = "subscription", type = Join.Type.LEFT_FETCH)
    fun findBySubscriptionIdOrderByCreatedAtDesc(subscriptionId: Long): List<WebhookDelivery>

    @Join(value = "subscription", type = Join.Type.LEFT_FETCH)
    fun findByStatus(status: WebhookDelivery.Status): List<WebhookDelivery>
}
