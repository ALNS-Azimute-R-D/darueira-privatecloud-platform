package de.legalhub

import io.micronaut.http.MutableHttpRequest
import io.micronaut.http.annotation.ClientFilter
import io.micronaut.http.annotation.RequestFilter
import jakarta.inject.Singleton

@ClientFilter("/**")
@Singleton
class AuthClientFilter {

    String accessToken

    @RequestFilter
    void filter(MutableHttpRequest<?> request) {
        if (accessToken) {
            request.bearerAuth(accessToken)
        }
    }
}
