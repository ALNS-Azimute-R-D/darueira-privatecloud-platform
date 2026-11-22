package de.legalhub.domains.account

import de.legalhub.adapters.output.messaging.RabbitEntityEventClient
import de.legalhub.adapters.output.repository.UserGroupRepository
import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.adapters.output.repository.UserRoleRepository
import de.legalhub.model.User
import de.legalhub.model.UserRole
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import io.micronaut.http.HttpStatus
import io.micronaut.http.exceptions.HttpStatusException
import jakarta.inject.Singleton
import jakarta.transaction.Transactional
import org.slf4j.LoggerFactory
import java.time.Instant

@Singleton
open class UserService(
    private val userRepository: UserRepository,
    private val userRoleRepository: UserRoleRepository,
    private val userGroupRepository: UserGroupRepository,
    private val rabbitEntityEventClient: RabbitEntityEventClient,
) {
    private val log = LoggerFactory.getLogger(UserService::class.java)

    @Transactional
    open fun create(cmd: UserCommands.Create): UserResponse {
        val email = cmd.email?.trim()?.lowercase()
            ?: throw HttpStatusException(HttpStatus.BAD_REQUEST, "Email is required")
        val password = cmd.password
            ?: throw HttpStatusException(HttpStatus.BAD_REQUEST, "Password is required")

        if (userRepository.findByEmail(email).isPresent) {
            throw HttpStatusException(HttpStatus.CONFLICT, "User with email '$email' already exists")
        }

        val user = User().apply {
            this.email = email
            this.firstname = cmd.firstname?.trim()
            this.lastname = cmd.lastname?.trim()
            this.password = password
            this.enabled = cmd.enabled
            this.createdAt = Instant.now()
            this.updatedAt = Instant.now()
        }

        val savedUser = userRepository.save(user)

        val rolesToSave = if (cmd.roles.isNotEmpty()) cmd.roles else listOf(UserRole.Role.CASEFORCE)
        val savedRoles = rolesToSave.distinct().map { role ->
            userRoleRepository.save(UserRole().apply {
                this.user = savedUser
                this.role = role
                this.createdAt = Instant.now()
            })
        }

        try {
            rabbitEntityEventClient.send(EntityEvent(EntityType.USER, savedUser.id!!))
        } catch (e: Exception) {
            log.warn("Could not publish USER CREATE event to RabbitMQ: {}", e.message)
        }

        return UserResponse.from(savedUser, savedRoles)
    }

    open fun get(id: Long): UserResponse? {
        val user = userRepository.findByIdAndDeletedAtIsNull(id).orElse(null) ?: return null
        val roles = userRoleRepository.findByUserId(user.id!!)
        return UserResponse.from(user, roles)
    }

    open fun getByEmail(email: String): UserResponse? {
        val user = userRepository.findByEmail(email.trim().lowercase()).orElse(null) ?: return null
        if (user.deletedAt != null) return null
        val roles = userRoleRepository.findByUserId(user.id!!)
        return UserResponse.from(user, roles)
    }

    open fun list(): List<UserResponse> {
        val users = userRepository.findByDeletedAtIsNull()
        return users.map { user ->
            val roles = userRoleRepository.findByUserId(user.id!!)
            UserResponse.from(user, roles)
        }
    }

    @Transactional
    open fun update(id: Long, cmd: UserCommands.Update): UserResponse {
        val user = userRepository.findByIdAndDeletedAtIsNull(id).orElseThrow {
            HttpStatusException(HttpStatus.NOT_FOUND, "User with ID $id not found")
        }

        cmd.email?.trim()?.lowercase()?.let { newEmail ->
            if (newEmail != user.email) {
                if (userRepository.findByEmail(newEmail).isPresent) {
                    throw HttpStatusException(HttpStatus.CONFLICT, "User with email '$newEmail' already exists")
                }
                user.email = newEmail
            }
        }

        cmd.firstname?.let { user.firstname = it.trim() }
        cmd.lastname?.let { user.lastname = it.trim() }
        cmd.password?.let { if (it.isNotBlank()) user.password = it }
        cmd.enabled?.let { user.enabled = it }
        user.updatedAt = Instant.now()

        val updatedUser = userRepository.update(user)

        val updatedRoles = if (cmd.roles != null) {
            userRoleRepository.deleteByUserId(updatedUser.id!!)
            cmd.roles!!.distinct().map { role ->
                userRoleRepository.save(UserRole().apply {
                    this.user = updatedUser
                    this.role = role
                    this.createdAt = Instant.now()
                })
            }
        } else {
            userRoleRepository.findByUserId(updatedUser.id!!)
        }

        try {
            rabbitEntityEventClient.send(EntityEvent(EntityType.USER, updatedUser.id!!))
        } catch (e: Exception) {
            log.warn("Could not publish USER UPDATE event to RabbitMQ: {}", e.message)
        }

        return UserResponse.from(updatedUser, updatedRoles)
    }

    @Transactional
    open fun delete(id: Long): Boolean {
        val user = userRepository.findByIdAndDeletedAtIsNull(id).orElseThrow {
            HttpStatusException(HttpStatus.NOT_FOUND, "User with ID $id not found")
        }

        user.deletedAt = Instant.now()
        user.enabled = false
        userRepository.update(user)

        // Remove group memberships for deleted user
        userGroupRepository.deleteByUserId(id)

        try {
            rabbitEntityEventClient.send(EntityEvent(EntityType.USER, id))
        } catch (e: Exception) {
            log.warn("Could not publish USER DELETE event to RabbitMQ: {}", e.message)
        }

        return true
    }
}
