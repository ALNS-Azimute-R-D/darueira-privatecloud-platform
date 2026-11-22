package de.legalhub.fakeagency.exception;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(CaseforceIntegrationException.class)
    public ResponseEntity<Map<String, Object>> handleCaseforceIntegrationException(CaseforceIntegrationException ex) {
        HttpStatusCode status = ex.getStatusCode() != null ? ex.getStatusCode() : HttpStatus.BAD_GATEWAY;
        log.error("Handling CaseforceIntegrationException [status={}]: {}", status, ex.getMessage());

        Map<String, Object> errorBody = new LinkedHashMap<>();
        errorBody.put("timestamp", Instant.now().toString());
        errorBody.put("status", status.value());
        errorBody.put("error", "CaseForce LegalHub Integration Failure");
        errorBody.put("message", ex.getMessage());
        if (ex.getResponseBody() != null && !ex.getResponseBody().isBlank()) {
            errorBody.put("upstreamResponse", ex.getResponseBody());
        }

        return ResponseEntity.status(status).body(errorBody);
    }
}
