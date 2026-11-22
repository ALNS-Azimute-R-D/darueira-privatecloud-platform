package de.legalhub.fakeagency.service;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

public class CaseforceAuthTokenServiceTest {

    @Test
    void shouldReturnNullWhenAuthIsDisabled() {
        CaseforceAuthTokenService service = new CaseforceAuthTokenService(
                "http://localhost:8080",
                false,
                "user@test.de",
                "password",
                "/login"
        );

        assertThat(service.getAccessToken()).isNull();
    }

    @Test
    void shouldHandleOfflineCaseforceGracefullyWithoutThrowing() {
        CaseforceAuthTokenService service = new CaseforceAuthTokenService(
                "http://localhost:65432", // unreachable port
                true,
                "fake-agency-client@legalhero.de",
                "FakeAgencyPass2026!",
                "/login"
        );

        String token = service.getAccessToken();
        assertThat(token).isNull();
    }

    @Test
    void shouldInvalidateCachedToken() {
        CaseforceAuthTokenService service = new CaseforceAuthTokenService(
                "http://localhost:8080",
                true,
                "fake-agency-client@legalhero.de",
                "FakeAgencyPass2026!",
                "/login"
        );

        service.invalidateToken();
        // Verifies no exceptions thrown
    }
}
