package de.legalhub.model

import io.micronaut.serde.annotation.Serdeable

@Serdeable
data class ListResult<T>(
    val list: List<T>,
    val totalCount: Long
)
