package de.legalhub.fakeagency.config;

import de.legalhub.fakeagency.service.CaseforceAuthTokenService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.stereotype.Component;

import java.io.IOException;

@Component
public class CaseforceAuthInterceptor implements ClientHttpRequestInterceptor {

    private static final Logger log = LoggerFactory.getLogger(CaseforceAuthInterceptor.class);

    private final CaseforceAuthTokenService tokenService;

    public CaseforceAuthInterceptor(CaseforceAuthTokenService tokenService) {
        this.tokenService = tokenService;
    }

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body, ClientHttpRequestExecution execution) throws IOException {
        String path = request.getURI().getPath();
        boolean isLoginRequest = (path != null && (path.endsWith("/login") || path.endsWith("/login-new")));

        if (!isLoginRequest) {
            String token = tokenService.getAccessToken();
            if (token != null && !token.isBlank()) {
                request.getHeaders().setBearerAuth(token);
            }
            log.info("CaseforceAuthInterceptor: Sending {} '{}' with Authorization header present={}",
                    request.getMethod(), request.getURI(), request.getHeaders().getFirst("Authorization") != null);
        }

        ClientHttpResponse response = execution.execute(request, body);

        if (!isLoginRequest && (response.getStatusCode().value() == 401 || response.getStatusCode().value() == 403)) {
            log.warn("Caseforce responded with status {} for '{}'. Invalidating token cache.",
                    response.getStatusCode(), request.getURI());
            tokenService.invalidateToken();
        }

        return response;
    }
}
