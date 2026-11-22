package de.legalhub.domains.auth

import io.micronaut.http.HttpStatus
import io.micronaut.http.exceptions.HttpStatusException

class MissingPermissionException : HttpStatusException(HttpStatus.FORBIDDEN, "Missing required permission")
