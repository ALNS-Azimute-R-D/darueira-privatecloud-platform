package de.legalhub.domains.auth

import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.adapters.output.repository.UserRoleRepository
import io.micronaut.http.HttpRequest
import io.micronaut.security.authentication.AuthenticationProvider
import io.micronaut.security.authentication.AuthenticationRequest
import io.micronaut.security.authentication.AuthenticationResponse
import jakarta.inject.Singleton
import org.reactivestreams.Publisher
import reactor.core.publisher.Flux

@Singleton
class AuthenticationProviderUserPassword(
    private val userRepository: UserRepository,
    private val userRoleRepository: UserRoleRepository,
) : AuthenticationProvider<HttpRequest<*>> {

    override fun authenticate(
        httpRequest: HttpRequest<*>?,
        authenticationRequest: AuthenticationRequest<*, *>
    ): Publisher<AuthenticationResponse> {
        val identity = authenticationRequest.identity as? String
        val secret = authenticationRequest.secret as? String

        if (identity == null || secret == null) {
            return Flux.empty()
        }

        val user = userRepository.findByEmail(identity).orElse(null)
            ?: return Flux.empty()

        if (!user.enabled || secret != user.password) {
            return Flux.empty()
        }

        val roles = userRoleRepository.findByUserId(user.id!!).map { it.role.name }
        return Flux.just(AuthenticationResponse.success(identity, roles))
    }
}
