package de.legalhub.fakeagency.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import java.time.LocalDate;
import java.util.List;

public class CaseforceOnboardingRequestDto {

    private String name;
    private String alias;
    private String email;
    private String status = "ACTIVE";
    private List<WebhookItemDto> webhooks;
    private List<CaseItemDto> cases;

    public CaseforceOnboardingRequestDto() {}

    public CaseforceOnboardingRequestDto(String name, String alias, String email, String status, List<WebhookItemDto> webhooks) {
        this.name = name;
        this.alias = alias;
        this.email = email;
        this.status = status;
        this.webhooks = webhooks;
    }

    public CaseforceOnboardingRequestDto(String name, String alias, String email, String status, List<WebhookItemDto> webhooks, List<CaseItemDto> cases) {
        this.name = name;
        this.alias = alias;
        this.email = email;
        this.status = status;
        this.webhooks = webhooks;
        this.cases = cases;
    }

    public static class WebhookItemDto {
        private String targetUrl;
        private String secret;
        private List<String> eventTypes;

        public WebhookItemDto() {}

        public WebhookItemDto(String targetUrl, String secret, List<String> eventTypes) {
            this.targetUrl = targetUrl;
            this.secret = secret;
            this.eventTypes = eventTypes;
        }

        public String getTargetUrl() {
            return targetUrl;
        }

        public void setTargetUrl(String targetUrl) {
            this.targetUrl = targetUrl;
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
    }

    public static class UserItemDto {
        private String email;
        private String firstname;
        private String lastname;
        private String password;
        private boolean enabled = true;
        private List<String> roles;

        public UserItemDto() {}

        public UserItemDto(String email, String firstname, String lastname) {
            this.email = email;
            this.firstname = firstname;
            this.lastname = lastname;
            this.enabled = true;
        }

        public UserItemDto(String email, String firstname, String lastname, String password, boolean enabled, List<String> roles) {
            this.email = email;
            this.firstname = firstname;
            this.lastname = lastname;
            this.password = password;
            this.enabled = enabled;
            this.roles = roles;
        }

        public String getEmail() {
            return email;
        }

        public void setEmail(String email) {
            this.email = email;
        }

        public String getFirstname() {
            return firstname;
        }

        public void setFirstname(String firstname) {
            this.firstname = firstname;
        }

        public String getLastname() {
            return lastname;
        }

        public void setLastname(String lastname) {
            this.lastname = lastname;
        }

        public String getPassword() {
            return password;
        }

        public void setPassword(String password) {
            this.password = password;
        }

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public List<String> getRoles() {
            return roles;
        }

        public void setRoles(List<String> roles) {
            this.roles = roles;
        }
    }

    public static class ActionItemDto {
        private String name;
        private boolean isTask;
        private String status = "OPEN";
        private UserItemDto assignee;
        @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
        private LocalDate dueDate;
        private String notes;

        public ActionItemDto() {}

        public ActionItemDto(String name, boolean isTask, String status, UserItemDto assignee, LocalDate dueDate, String notes) {
            this.name = name;
            this.isTask = isTask;
            this.status = status;
            this.assignee = assignee;
            this.dueDate = dueDate;
            this.notes = notes;
        }

        public String getName() {
            return name;
        }

        public void setName(String name) {
            this.name = name;
        }

        public boolean isTask() {
            return isTask;
        }

        public void setTask(boolean task) {
            isTask = task;
        }

        public String getStatus() {
            return status;
        }

        public void setStatus(String status) {
            this.status = status;
        }

        public UserItemDto getAssignee() {
            return assignee;
        }

        public void setAssignee(UserItemDto assignee) {
            this.assignee = assignee;
        }

        public LocalDate getDueDate() {
            return dueDate;
        }

        public void setDueDate(LocalDate dueDate) {
            this.dueDate = dueDate;
        }

        public String getNotes() {
            return notes;
        }

        public void setNotes(String notes) {
            this.notes = notes;
        }
    }

    public static class CaseItemDto {
        private String caseNumber;
        private String legalField;
        private String status = "OPEN";
        private String summary;
        private UserItemDto lawyer;
        private UserItemDto assignee;
        private List<ActionItemDto> actions;

        public CaseItemDto() {}

        public CaseItemDto(String caseNumber, String legalField, String status, String summary, UserItemDto lawyer, UserItemDto assignee, List<ActionItemDto> actions) {
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

        public UserItemDto getLawyer() {
            return lawyer;
        }

        public void setLawyer(UserItemDto lawyer) {
            this.lawyer = lawyer;
        }

        public UserItemDto getAssignee() {
            return assignee;
        }

        public void setAssignee(UserItemDto assignee) {
            this.assignee = assignee;
        }

        public List<ActionItemDto> getActions() {
            return actions;
        }

        public void setActions(List<ActionItemDto> actions) {
            this.actions = actions;
        }
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getAlias() {
        return alias;
    }

    public void setAlias(String alias) {
        this.alias = alias;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public List<WebhookItemDto> getWebhooks() {
        return webhooks;
    }

    public void setWebhooks(List<WebhookItemDto> webhooks) {
        this.webhooks = webhooks;
    }

    public List<CaseItemDto> getCases() {
        return cases;
    }

    public void setCases(List<CaseItemDto> cases) {
        this.cases = cases;
    }
}
