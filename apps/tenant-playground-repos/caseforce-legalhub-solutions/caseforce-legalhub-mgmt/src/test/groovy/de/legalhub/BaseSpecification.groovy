package de.legalhub

import de.legalhub.domains.auth.Permission
import de.legalhub.model.Group
import de.legalhub.model.PartnerAgency
import de.legalhub.model.User
import de.legalhub.model.UserGroup
import de.legalhub.model.UserRole
import de.legalhub.adapters.output.repository.GroupRepository
import de.legalhub.adapters.output.repository.LegalCaseRepository
import de.legalhub.adapters.output.repository.ActionRepository
import de.legalhub.adapters.output.repository.PartnerAgencyRepository
import de.legalhub.adapters.output.repository.UserGroupRepository
import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.adapters.output.repository.UserRoleRepository
import de.legalhub.adapters.output.messaging.RabbitEntityEventClient
import io.micronaut.http.HttpRequest
import io.micronaut.http.client.HttpClient
import io.micronaut.http.client.annotation.Client
import io.micronaut.test.annotation.MockBean
import io.micronaut.test.extensions.spock.annotation.MicronautTest
import jakarta.inject.Inject
import spock.lang.AutoCleanup
import spock.lang.Shared
import spock.lang.Specification

@MicronautTest(transactional = false)
abstract class BaseSpecification extends Specification {

    @Shared @AutoCleanup @Inject @Client("/") HttpClient apiClient
    @Shared @Inject AuthClientFilter authClientFilter
    @Shared @Inject UserRepository userRepository
    @Shared @Inject UserRoleRepository userRoleRepository
    @Shared @Inject GroupRepository groupRepository
    @Shared @Inject UserGroupRepository userGroupRepository
    @Shared @Inject PartnerAgencyRepository partnerAgencyRepository
    @Shared @Inject LegalCaseRepository legalCaseRepository
    @Shared @Inject ActionRepository actionRepository

    @Shared User user
    @Shared PartnerAgency agency
    @Shared String accessToken

    static final String EMAIL = "test@legalhero.de"
    static final String PASSWORD = "TestPass123"

    void setupSpec() {
        agency = partnerAgencyRepository.save(new PartnerAgency(
            name: "Test Agency",
            alias: "test-agency",
            status: PartnerAgency.Status.ACTIVE
        ))

        user = userRepository.save(new User(
            email: EMAIL,
            password: PASSWORD,
            firstname: "Max",
            lastname: "Mustermann",
            enabled: true
        ))

        userRoleRepository.save(new UserRole(
            role: UserRole.Role.ROOT,
            user: user
        ))

        def group = groupRepository.save(new Group(
            name: "Admin",
            permissions: Permission.values().collect { it.name() }
        ))

        userGroupRepository.save(new UserGroup(
            user: user,
            group: group
        ))

        // Login and get JWT token
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/login", [username: EMAIL, password: PASSWORD]),
            Map
        )
        accessToken = response.body().access_token ?: response.body().accessToken
        authClientFilter.accessToken = accessToken
    }

    def cleanup() {
        // Override in subclasses for per-test cleanup
    }

    // RabbitMQ is disabled in tests, mock the client
    @MockBean(RabbitEntityEventClient)
    RabbitEntityEventClient rabbitEntityEventClient() {
        Mock(RabbitEntityEventClient)
    }
}
