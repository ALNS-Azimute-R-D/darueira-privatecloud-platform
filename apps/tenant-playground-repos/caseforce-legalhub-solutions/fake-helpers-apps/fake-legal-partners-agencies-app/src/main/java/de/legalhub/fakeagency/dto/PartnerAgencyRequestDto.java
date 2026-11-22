package de.legalhub.fakeagency.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Pattern;

import java.util.List;

@Schema(description = "Partner Agency onboarding request payload for fake simulator")
public class PartnerAgencyRequestDto {

    @Pattern(regexp = "^[a-zA-Z0-9_-]+$", message = "Alias must only contain alphanumeric characters, underscores or hyphens")
    @Schema(description = "Unique alphanumeric slug/alias identifier for the agency", example = "berlin-legal-partners")
    private String alias;

    @Schema(description = "Business name of the partner agency", example = "Berlin Legal Partners GmbH")
    private String name;

    @Schema(description = "Primary contact email address", example = "contact@berlin-legal.de")
    private String email;

    @Schema(description = "Optional custom HMAC secret key. If omitted, a secure 'whsec_...' key is auto-generated.", example = "whsec_custom_secret_123")
    private String secret;

    @Schema(description = "List of event types to subscribe to", example = "[\"LEGAL_CASE_CREATED\", \"LEGAL_CASE_UPDATED\", \"ACTION_CREATED\", \"ACTION_UPDATED\"]")
    private List<String> eventTypes;

    @Schema(description = "Collection of legal cases (with lawyer, assignee, and actions) to provision with the agency")
    private List<LegalCaseDto> cases;
    private List<LegalCaseDto> legalCases;

    public PartnerAgencyRequestDto() {}

    public PartnerAgencyRequestDto(String alias, String name, String email, String secret, List<String> eventTypes) {
        this.alias = alias;
        this.name = name;
        this.email = email;
        this.secret = secret;
        this.eventTypes = eventTypes;
    }

    public PartnerAgencyRequestDto(String alias, String name, String email, String secret, List<String> eventTypes, List<LegalCaseDto> legalCases) {
        this.alias = alias;
        this.name = name;
        this.email = email;
        this.secret = secret;
        this.eventTypes = eventTypes;
        this.legalCases = legalCases;
        this.cases = legalCases;
    }

    public String getAlias() {
        return alias;
    }

    public void setAlias(String alias) {
        this.alias = alias;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getSecret() {
        return secret;
    }

    public void setSecret(String secret) {
        this.secret = secret;
    }

    public List<String> getEventTypes() {
        return eventTypes;
    }

    public void setEventTypes(List<String> eventTypes) {
        this.eventTypes = eventTypes;
    }

    public List<LegalCaseDto> getCases() {
        return cases != null && !cases.isEmpty() ? cases : legalCases;
    }

    public void setCases(List<LegalCaseDto> cases) {
        this.cases = cases;
        if (this.legalCases == null) {
            this.legalCases = cases;
        }
    }

    public List<LegalCaseDto> getLegalCases() {
        return getCases();
    }

    public void setLegalCases(List<LegalCaseDto> legalCases) {
        this.legalCases = legalCases;
        if (this.cases == null) {
            this.cases = legalCases;
        }
    }
}
