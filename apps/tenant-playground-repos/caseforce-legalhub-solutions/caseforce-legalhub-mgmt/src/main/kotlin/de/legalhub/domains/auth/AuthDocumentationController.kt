package de.legalhub.domains.auth

import io.micronaut.context.event.ApplicationEventPublisher
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpResponse
import io.micronaut.http.HttpStatus
import io.micronaut.http.MediaType
import io.micronaut.http.MutableHttpResponse
import io.micronaut.http.annotation.Body
import io.micronaut.http.annotation.Controller
import io.micronaut.http.annotation.Post
import io.micronaut.security.annotation.Secured
import io.micronaut.security.authentication.Authentication
import io.micronaut.security.authentication.AuthenticationFailureReason
import io.micronaut.security.authentication.AuthenticationResponse
import io.micronaut.security.authentication.Authenticator
import io.micronaut.security.authentication.UsernamePasswordCredentials
import io.micronaut.security.event.LoginFailedEvent
import io.micronaut.security.event.LoginSuccessfulEvent
import io.micronaut.security.rules.SecurityRule
import io.micronaut.security.token.generator.TokenGenerator
import io.micronaut.serde.annotation.Serdeable
import io.swagger.v3.oas.annotations.Operation
import io.swagger.v3.oas.annotations.media.Content
import io.swagger.v3.oas.annotations.media.Schema
import io.swagger.v3.oas.annotations.parameters.RequestBody
import io.swagger.v3.oas.annotations.responses.ApiResponse
import io.swagger.v3.oas.annotations.security.SecurityRequirements
import io.swagger.v3.oas.annotations.tags.Tag
import jakarta.validation.Valid
import reactor.core.publisher.Mono

@Serdeable
data class LoginRequest(
    @field:Schema(description = "User email address", example = "admin@legalhero.de", required = true)
    val username: String,
    @field:Schema(description = "User password", example = "TestPass123", required = true)
    val password: String
)

@Serdeable
data class LoginResponse(
    @field:Schema(description = "JWT Bearer access token", example = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    val access_token: String,
    @field:Schema(description = "Token type", example = "Bearer")
    val token_type: String = "Bearer",
    @field:Schema(description = "Token expiration in seconds", example = "3600")
    val expires_in: Int = 3600,
    @field:Schema(description = "User assigned roles", example = "[\"ROOT\"]")
    val roles: List<String> = emptyList()
)

@Tag(name = "Authentication", description = "JWT Token Generation and Authentication Operations")
@Controller
@Secured(SecurityRule.IS_ANONYMOUS)
class AuthDocumentationController(
    private val authenticator: Authenticator<HttpRequest<*>>,
    private val tokenGenerator: TokenGenerator,
    private val loginSuccessfulEventPublisher: ApplicationEventPublisher<LoginSuccessfulEvent>,
    private val loginFailedEventPublisher: ApplicationEventPublisher<LoginFailedEvent>
) {

    @Operation(
        summary = "Authenticate user and obtain JWT Bearer Token (Custom Swagger-friendly endpoint)",
        description = "Custom endpoint to obtain a JWT Bearer access token for authenticating subsequent API requests. Default admin credentials: username='admin@legalhero.de', password='TestPass123'."
    )
    @SecurityRequirements
    @ApiResponse(
        responseCode = "200",
        description = "Successfully authenticated. Returns JWT access token.",
        content = [Content(mediaType = MediaType.APPLICATION_JSON, schema = Schema(implementation = LoginResponse::class))]
    )
    @ApiResponse(
        responseCode = "401",
        description = "Invalid credentials supplied or user disabled"
    )
    @Post("/login-new", produces = [MediaType.APPLICATION_JSON], consumes = [MediaType.APPLICATION_JSON])
    fun login(
        @RequestBody(description = "User credentials", required = true)
        @Body @Valid requestBody: LoginRequest,
        request: HttpRequest<*>
    ): Mono<MutableHttpResponse<*>> {
        val credentials = UsernamePasswordCredentials(requestBody.username, requestBody.password)
        return Mono.from(authenticator.authenticate(request, credentials))
            .map { response: AuthenticationResponse ->
                if (response.isAuthenticated) {
                    val authentication = if (response is Authentication) {
                        response
                    } else if (response.authentication.isPresent) {
                        response.authentication.get()
                    } else {
                        val rolesList: List<String> = emptyList()
                        Authentication.build(requestBody.username, rolesList)
                    }

                    loginSuccessfulEventPublisher.publishEvent(LoginSuccessfulEvent(authentication))
                    val claims = mutableMapOf<String, Any>(
                        "sub" to authentication.name,
                        "roles" to (authentication.roles?.toList() ?: emptyList())
                    )
                    authentication.attributes?.let { claims.putAll(it) }

                    val tokenOpt = tokenGenerator.generateToken(claims)
                    if (tokenOpt.isPresent) {
                        val roles = authentication.roles?.toList() ?: emptyList()
                        val loginResponse = LoginResponse(
                            access_token = tokenOpt.get(),
                            token_type = "Bearer",
                            expires_in = 3600,
                            roles = roles
                        )
                        HttpResponse.ok(loginResponse)
                    } else {
                        loginFailedEventPublisher.publishEvent(LoginFailedEvent(AuthenticationResponse.failure("Token generation failed")))
                        HttpResponse.status<Any>(HttpStatus.UNAUTHORIZED).body(mapOf("message" to "Token generation failed"))
                    }
                } else {
                    val msg = response.message.orElse(AuthenticationFailureReason.CREDENTIALS_DO_NOT_MATCH.name)
                    loginFailedEventPublisher.publishEvent(LoginFailedEvent(response))
                    HttpResponse.status<Any>(HttpStatus.UNAUTHORIZED).body(mapOf("message" to msg))
                }
            }
            .defaultIfEmpty(
                HttpResponse.status<Any>(HttpStatus.UNAUTHORIZED).body(mapOf("message" to AuthenticationFailureReason.USER_NOT_FOUND.name))
            )
    }
}
