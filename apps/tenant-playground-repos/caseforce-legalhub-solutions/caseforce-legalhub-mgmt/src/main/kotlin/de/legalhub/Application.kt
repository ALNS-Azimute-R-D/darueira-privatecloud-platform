package de.legalhub

import io.micronaut.runtime.Micronaut
import io.swagger.v3.oas.annotations.OpenAPIDefinition
import io.swagger.v3.oas.annotations.enums.SecuritySchemeType
import io.swagger.v3.oas.annotations.info.Contact
import io.swagger.v3.oas.annotations.info.Info
import io.swagger.v3.oas.annotations.security.SecurityRequirement
import io.swagger.v3.oas.annotations.security.SecurityScheme

@OpenAPIDefinition(
    info = Info(
        title = "CaseForce Legal Hub API",
        version = "1.0.0",
        description = "CaseForce Backend Platform API for Law Firms and Partner Agencies - Legal Case Management, Event-Driven Webhooks & Bulk Operations",
        contact = Contact(name = "CaseForce Engineering Team", email = "dev@caseforce.legalhero.de")
    ),
    security = [SecurityRequirement(name = "BearerAuth")]
)
@SecurityScheme(
    name = "BearerAuth",
    type = SecuritySchemeType.HTTP,
    scheme = "bearer",
    bearerFormat = "JWT",
    description = "Enter JWT access token obtained from /login endpoint"
)
object Application {
    @JvmStatic
    fun main(args: Array<String>) {
        Micronaut.run(Application.javaClass, *args)
    }
}

fun main(args: Array<String>) {
    Micronaut.run(*args)
}

