package de.legalhub.fakeagency.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.Map;

@Service
public class CaseforceAuthTokenService {

    private static final Logger log = LoggerFactory.getLogger(CaseforceAuthTokenService.class);

    private final String baseUrl;
    private final boolean authEnabled;
    private final String username;
    private final String password;
    private final String loginEndpoint;
    private final RestClient authRestClient;

    private String cachedAccessToken;
    private Instant tokenExpiresAt;

    public CaseforceAuthTokenService(
            @Value("${caseforce.api.base-url:http://localhost:8080}") String baseUrl,
            @Value("${caseforce.api.auth.enabled:true}") boolean authEnabled,
            @Value("${caseforce.api.auth.username:fake-agency-client@legalhero.de}") String username,
            @Value("${caseforce.api.auth.password:FakeAgencyPass2026!}") String password,
            @Value("${caseforce.api.auth.login-endpoint:/login}") String loginEndpoint
    ) {
        this.baseUrl = baseUrl;
        this.authEnabled = authEnabled;
        this.username = username;
        this.password = password;
        this.loginEndpoint = loginEndpoint;
        this.authRestClient = RestClient.builder().build();
    }

    public synchronized String getAccessToken() {
        if (!authEnabled) {
            return null;
        }

        if (cachedAccessToken != null && tokenExpiresAt != null
                && Instant.now().isBefore(tokenExpiresAt.minusSeconds(30))) {
            return cachedAccessToken;
        }

        return requestNewAccessToken();
    }

    public synchronized void invalidateToken() {
        this.cachedAccessToken = null;
        this.tokenExpiresAt = null;
    }

    private String requestNewAccessToken() {
        String effectiveBaseUrl = (baseUrl != null ? baseUrl.replaceAll("/+$", "") : "http://localhost:8080");
        String effectiveLoginEndpoint = (loginEndpoint != null ? (loginEndpoint.startsWith("/") ? loginEndpoint : "/" + loginEndpoint) : "/login");
        String targetLoginUri = effectiveBaseUrl + effectiveLoginEndpoint;

        log.info("Authenticating Fake Agency service against CaseForce LegalHub at '{}' with username '{}'",
                targetLoginUri, username);

        try {
            Map<String, String> loginPayload = Map.of(
                    "username", username,
                    "password", password
            );

            Map<?, ?> response = authRestClient.post()
                    .uri(targetLoginUri)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(loginPayload)
                    .retrieve()
                    .body(Map.class);

            if (response != null) {
                Object tokenObj = response.get("access_token");
                if (tokenObj == null) {
                    tokenObj = response.get("accessToken");
                }

                if (tokenObj != null) {
                    this.cachedAccessToken = tokenObj.toString();
                    long expiresInSeconds = 3600;
                    Object expObj = response.get("expires_in");
                    if (expObj instanceof Number num) {
                        expiresInSeconds = num.longValue();
                    }
                    this.tokenExpiresAt = Instant.now().plusSeconds(expiresInSeconds);
                    log.info("Successfully obtained JWT access token for service user '{}' (expires in {}s)",
                            username, expiresInSeconds);
                    return this.cachedAccessToken;
                }
            }
            log.warn("Login response from CaseForce did not contain an access_token: {}", response);
        } catch (Exception e) {
            log.warn("Could not authenticate against CaseForce LegalHub (offline or mocked): {}", e.getMessage());
        }

        return null;
    }
}
