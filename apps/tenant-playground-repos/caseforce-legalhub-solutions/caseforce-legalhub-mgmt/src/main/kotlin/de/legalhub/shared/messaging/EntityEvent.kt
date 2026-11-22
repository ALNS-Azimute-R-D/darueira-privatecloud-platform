package de.legalhub.shared.messaging

import io.micronaut.serde.annotation.Serdeable

@Serdeable
data class EntityEvent(
    val entityType: EntityType,
    val entityId: Long
)
