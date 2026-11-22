package de.legalhub.fakeagency.exception;

import org.springframework.http.HttpStatusCode;

/**
 * Exception thrown when communication or contract verification with CaseForce LegalHub fails.
 */
public class CaseforceIntegrationException extends RuntimeException {

    private final HttpStatusCode statusCode;
    private final String responseBody;

    public CaseforceIntegrationException(String message, HttpStatusCode statusCode, String responseBody, Throwable cause) {
        super(message, cause);
        this.statusCode = statusCode;
        this.responseBody = responseBody;
    }

    public CaseforceIntegrationException(String message, Throwable cause) {
        super(message, cause);
        this.statusCode = null;
        this.responseBody = null;
    }

    public HttpStatusCode getStatusCode() {
        return statusCode;
    }

    public String getResponseBody() {
        return responseBody;
    }
}
