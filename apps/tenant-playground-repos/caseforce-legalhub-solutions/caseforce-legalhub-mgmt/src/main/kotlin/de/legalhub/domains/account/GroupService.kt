package de.legalhub.domains.account

import de.legalhub.adapters.output.messaging.RabbitEntityEventClient
import de.legalhub.adapters.output.repository.GroupRepository
import de.legalhub.adapters.output.repository.UserGroupRepository
import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.adapters.output.repository.UserRoleRepository
import de.legalhub.model.Group
import de.legalhub.model.UserGroup
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import io.micronaut.http.HttpStatus
import io.micronaut.http.exceptions.HttpStatusException
import jakarta.inject.Singleton
import jakarta.transaction.Transactional
import org.slf4j.LoggerFactory
import java.time.Instant

@Singleton
open class GroupService(
    private val groupRepository: GroupRepository,
    private val userGroupRepository: UserGroupRepository,
    private val userRepository: UserRepository,
    private val userRoleRepository: UserRoleRepository,
    private val rabbitEntityEventClient: RabbitEntityEventClient,
) {
    private val log = LoggerFactory.getLogger(GroupService::class.java)

    @Transactional
    open fun create(cmd: GroupCommands.Create): GroupResponse {
        val name = cmd.name?.trim()
            ?: throw HttpStatusException(HttpStatus.BAD_REQUEST, "Group name is required")

        if (groupRepository.findByName(name).isPresent) {
            throw HttpStatusException(HttpStatus.CONFLICT, "Group with name '$name' already exists")
        }

        val group = Group().apply {
            this.name = name
            this.permissions = cmd.permissions.distinct()
            this.createdAt = Instant.now()
            this.updatedAt = Instant.now()
        }

        val savedGroup = groupRepository.save(group)

        try {
            rabbitEntityEventClient.send(EntityEvent(EntityType.GROUP, savedGroup.id!!))
        } catch (e: Exception) {
            log.warn("Could not publish GROUP CREATE event to RabbitMQ: {}", e.message)
        }

        return GroupResponse.from(savedGroup, 0L)
    }

    open fun get(id: Long): GroupResponse? {
        val group = groupRepository.findById(id).orElse(null) ?: return null
        val count = userGroupRepository.countByGroupId(id)
        return GroupResponse.from(group, count)
    }

    open fun list(): List<GroupResponse> {
        val groups = groupRepository.findAll()
        return groups.map { group ->
            val count = userGroupRepository.countByGroupId(group.id!!)
            GroupResponse.from(group, count)
        }
    }

    @Transactional
    open fun update(id: Long, cmd: GroupCommands.Update): GroupResponse {
        val group = groupRepository.findById(id).orElseThrow {
            HttpStatusException(HttpStatus.NOT_FOUND, "Group with ID $id not found")
        }

        cmd.name?.trim()?.let { newName ->
            if (newName != group.name) {
                if (groupRepository.findByName(newName).isPresent) {
                    throw HttpStatusException(HttpStatus.CONFLICT, "Group with name '$newName' already exists")
                }
                group.name = newName
            }
        }

        cmd.permissions?.let {
            group.permissions = it.distinct()
        }

        group.updatedAt = Instant.now()
        val updated = groupRepository.update(group)
        val count = userGroupRepository.countByGroupId(id)

        try {
            rabbitEntityEventClient.send(EntityEvent(EntityType.GROUP, updated.id!!))
        } catch (e: Exception) {
            log.warn("Could not publish GROUP UPDATE event to RabbitMQ: {}", e.message)
        }

        return GroupResponse.from(updated, count)
    }

    @Transactional
    open fun delete(id: Long): Boolean {
        if (!groupRepository.existsById(id)) {
            throw HttpStatusException(HttpStatus.NOT_FOUND, "Group with ID $id not found")
        }

        userGroupRepository.deleteByGroupId(id)
        groupRepository.deleteById(id)

        try {
            rabbitEntityEventClient.send(EntityEvent(EntityType.GROUP, id))
        } catch (e: Exception) {
            log.warn("Could not publish GROUP DELETE event to RabbitMQ: {}", e.message)
        }

        return true
    }

    @Transactional
    open fun addMember(groupId: Long, userId: Long): UserGroupMembershipResponse {
        val group = groupRepository.findById(groupId).orElseThrow {
            HttpStatusException(HttpStatus.NOT_FOUND, "Group with ID $groupId not found")
        }

        val user = userRepository.findByIdAndDeletedAtIsNull(userId).orElseThrow {
            HttpStatusException(HttpStatus.NOT_FOUND, "User with ID $userId not found")
        }

        val existing = userGroupRepository.findByUserIdAndGroupId(userId, groupId)
        if (existing.isPresent) {
            return UserGroupMembershipResponse.from(existing.get(), user, group)
        }

        val membership = userGroupRepository.save(UserGroup().apply {
            this.user = user
            this.group = group
        })

        log.info("User '{}' (ID={}) added to group '{}' (ID={})", user.email, userId, group.name, groupId)
        return UserGroupMembershipResponse.from(membership, user, group)
    }

    @Transactional
    open fun removeMember(groupId: Long, userId: Long): Boolean {
        if (!groupRepository.existsById(groupId)) {
            throw HttpStatusException(HttpStatus.NOT_FOUND, "Group with ID $groupId not found")
        }
        if (!userRepository.existsById(userId)) {
            throw HttpStatusException(HttpStatus.NOT_FOUND, "User with ID $userId not found")
        }

        val deleted = userGroupRepository.deleteByUserIdAndGroupId(userId, groupId)
        log.info("User ID={} removed from group ID={}, rows affected={}", userId, groupId, deleted)
        return deleted > 0
    }

    open fun listGroupMembers(groupId: Long): List<UserResponse> {
        if (!groupRepository.existsById(groupId)) {
            throw HttpStatusException(HttpStatus.NOT_FOUND, "Group with ID $groupId not found")
        }

        val memberships = userGroupRepository.findByGroupId(groupId)
        return memberships.mapNotNull { m ->
            val userId = m.user?.id ?: return@mapNotNull null
            val user = userRepository.findByIdAndDeletedAtIsNull(userId).orElse(null) ?: return@mapNotNull null
            val roles = userRoleRepository.findByUserId(userId)
            UserResponse.from(user, roles)
        }
    }

    open fun listUserGroups(userId: Long): List<GroupResponse> {
        if (!userRepository.existsById(userId)) {
            throw HttpStatusException(HttpStatus.NOT_FOUND, "User with ID $userId not found")
        }

        val memberships = userGroupRepository.findByUserId(userId)
        return memberships.mapNotNull { m ->
            val groupId = m.group?.id ?: return@mapNotNull null
            val group = groupRepository.findById(groupId).orElse(null) ?: return@mapNotNull null
            val count = userGroupRepository.countByGroupId(groupId)
            GroupResponse.from(group, count)
        }
    }
}
