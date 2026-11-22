package de.legalhub.domains.auth

import de.legalhub.model.UserRole
import de.legalhub.adapters.output.repository.UserGroupRepository
import de.legalhub.adapters.output.repository.UserRepository
import io.micronaut.aop.MethodInterceptor
import io.micronaut.aop.MethodInvocationContext
import io.micronaut.context.annotation.Requires
import io.micronaut.security.utils.SecurityService
import jakarta.inject.Singleton
import org.slf4j.LoggerFactory

@Singleton
@Requires(property = "micronaut.security.enabled", value = "true", defaultValue = "true")
class NeedsPermissionInterceptor(
    private val securityService: SecurityService,
    private val userRepository: UserRepository,
    private val userGroupRepository: UserGroupRepository
) : MethodInterceptor<Any?, Any?> {

    private val log = LoggerFactory.getLogger(NeedsPermissionInterceptor::class.java)

    override fun intercept(context: MethodInvocationContext<Any?, Any?>): Any? {
        val required = context.getValue(NeedsPermission::class.java, Permission::class.java)
            .orElseThrow { Exception("Missing annotation value on ${context.methodName}") }

        val auth = securityService.authentication.orElseThrow {
            log.warn("Access denied on {}: No authentication present", context.methodName)
            MissingPermissionException()
        }

        // ROOT role bypasses all permission checks (handles ROOT, ROLE_ROOT, case-insensitive)
        val isRoot = auth.roles.any { role ->
            role.equals(UserRole.Role.ROLE_ROOT, ignoreCase = true) ||
            role.equals("ROLE_${UserRole.Role.ROLE_ROOT}", ignoreCase = true)
        }
        if (isRoot) {
            log.debug("Access granted on {} for ROOT user '{}'", context.methodName, auth.name)
            return context.proceed()
        }

        val user = userRepository.findByEmail(auth.name).orElse(null)
        if (user == null || user.id == null) {
            log.warn("Access denied on {}: User '{}' not found in database", context.methodName, auth.name)
            throw MissingPermissionException()
        }

        val hasPermission = userGroupRepository.hasPermission(user.id!!, required.name)
        if (hasPermission) {
            log.debug("Access granted on {} for user '{}' with permission {}", context.methodName, auth.name, required.name)
            return context.proceed()
        }

        log.warn("Access denied on {}: User '{}' (id={}) lacks permission {}", context.methodName, auth.name, user.id, required.name)
        throw MissingPermissionException()
    }
}
