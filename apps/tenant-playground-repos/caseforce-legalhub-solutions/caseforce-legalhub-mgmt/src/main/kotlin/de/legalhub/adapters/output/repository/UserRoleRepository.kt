package de.legalhub.adapters.output.repository

import de.legalhub.model.UserRole
import io.micronaut.data.annotation.Query
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository

@JdbcRepository(dialect = Dialect.MYSQL)
interface UserRoleRepository : CrudRepository<UserRole, Long> {

    fun findByUserId(userId: Long): List<UserRole>

    @Query("DELETE FROM tb_user_role WHERE user_id = :userId")
    fun deleteByUserId(userId: Long): Long
}
