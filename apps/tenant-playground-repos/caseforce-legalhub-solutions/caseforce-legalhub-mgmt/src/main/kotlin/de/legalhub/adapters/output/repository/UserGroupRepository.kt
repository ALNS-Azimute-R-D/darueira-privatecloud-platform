package de.legalhub.adapters.output.repository

import de.legalhub.model.UserGroup
import io.micronaut.data.annotation.Query
import io.micronaut.data.jdbc.annotation.JdbcRepository
import io.micronaut.data.model.query.builder.sql.Dialect
import io.micronaut.data.repository.CrudRepository
import java.util.Optional

@JdbcRepository(dialect = Dialect.MYSQL)
interface UserGroupRepository : CrudRepository<UserGroup, Long> {

    @Query(
        """
        SELECT COUNT(*) > 0 FROM tb_user_group ug
        JOIN tb_permission_group g ON ug.group_id = g.id
        WHERE ug.user_id = :userId
        AND JSON_CONTAINS(g.js_permissions, CONCAT('"', :permission, '"'))
        """
    )
    fun hasPermission(userId: Long, permission: String): Boolean

    fun findByUserId(userId: Long): List<UserGroup>

    fun findByGroupId(groupId: Long): List<UserGroup>

    @Query("SELECT ug.* FROM tb_user_group ug WHERE ug.user_id = :userId AND ug.group_id = :groupId")
    fun findByUserIdAndGroupId(userId: Long, groupId: Long): Optional<UserGroup>

    @Query("DELETE FROM tb_user_group WHERE user_id = :userId AND group_id = :groupId")
    fun deleteByUserIdAndGroupId(userId: Long, groupId: Long): Long

    @Query("DELETE FROM tb_user_group WHERE user_id = :userId")
    fun deleteByUserId(userId: Long): Long

    @Query("DELETE FROM tb_user_group WHERE group_id = :groupId")
    fun deleteByGroupId(groupId: Long): Long

    @Query("SELECT COUNT(*) FROM tb_user_group WHERE group_id = :groupId")
    fun countByGroupId(groupId: Long): Long
}
