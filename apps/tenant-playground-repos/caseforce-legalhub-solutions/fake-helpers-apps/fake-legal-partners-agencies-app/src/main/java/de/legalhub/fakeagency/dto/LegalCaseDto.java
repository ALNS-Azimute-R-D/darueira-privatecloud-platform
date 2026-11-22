package de.legalhub.fakeagency.dto;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "Legal Case payload with lawyer, assignee, and actions for agency onboarding")
public class LegalCaseDto {

    @Schema(description = "Case number (auto-generated if omitted)", example = "CASE-BER-001")
    private String caseNumber;

    @Schema(description = "Legal field or practice area", example = "Labor Law")
    private String legalField;

    @Schema(description = "Status of the legal case", example = "OPEN")
    private String status = "OPEN";

    @Schema(description = "Summary or description of the case", example = "Wrongful termination litigation file")
    private String summary;

    @Schema(description = "Lawyer user details (looked up by email or created)")
    private UserDto lawyer;

    @Schema(description = "Assignee user details (looked up by email or created)")
    private UserDto assignee;

    @Schema(description = "Collection of actions or tasks for this case")
    private List<ActionDto> actions;

    public LegalCaseDto() {}

    public LegalCaseDto(String caseNumber, String legalField, String status, String summary, UserDto lawyer, UserDto assignee, List<ActionDto> actions) {
        this.caseNumber = caseNumber;
        this.legalField = legalField;
        this.status = status;
        this.summary = summary;
        this.lawyer = lawyer;
        this.assignee = assignee;
        this.actions = actions;
    }

    public String getCaseNumber() {
        return caseNumber;
    }

    public void setCaseNumber(String caseNumber) {
        this.caseNumber = caseNumber;
    }

    public String getLegalField() {
        return legalField;
    }

    public void setLegalField(String legalField) {
        this.legalField = legalField;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public UserDto getLawyer() {
        return lawyer;
    }

    public void setLawyer(UserDto lawyer) {
        this.lawyer = lawyer;
    }

    public UserDto getAssignee() {
        return assignee;
    }

    public void setAssignee(UserDto assignee) {
        this.assignee = assignee;
    }

    public List<ActionDto> getActions() {
        return actions;
    }

    public void setActions(List<ActionDto> actions) {
        this.actions = actions;
    }
}
