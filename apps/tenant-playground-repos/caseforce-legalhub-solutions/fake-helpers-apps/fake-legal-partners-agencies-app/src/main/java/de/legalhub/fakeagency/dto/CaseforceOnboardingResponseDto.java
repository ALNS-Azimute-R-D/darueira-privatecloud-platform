package de.legalhub.fakeagency.dto;

import java.time.Instant;
import java.util.List;

public class CaseforceOnboardingResponseDto {

    private Long id;
    private String alias;
    private String name;
    private String email;
    private String status;
    private Instant createdAt;
    private Instant updatedAt;
    private List<WebhookSubscriptionItemResponseDto> webhooks;
    private List<CaseResponseDto> cases;

    public static class WebhookSubscriptionItemResponseDto {
        private Long id;
        private Long partnerAgencyId;
        private String targetUrl;
        private String secret;
        private List<String> eventTypes;
        private String status;

        public Long getId() {
            return id;
        }

        public void setId(Long id) {
            this.id = id;
        }

        public Long getPartnerAgencyId() {
            return partnerAgencyId;
        }

        public void setPartnerAgencyId(Long partnerAgencyId) {
            this.partnerAgencyId = partnerAgencyId;
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

        public String getStatus() {
            return status;
        }

        public void setStatus(String status) {
            this.status = status;
        }
    }

    public static class CaseResponseDto {
        private Long id;
        private String caseNumber;
        private String legalField;
        private String status;
        private String summary;
        private Long lawyerId;
        private Long assigneeId;
        private Long partnerAgencyId;
        private Instant dateCreated;

        public Long getId() {
            return id;
        }

        public void setId(Long id) {
            this.id = id;
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

        public Long getLawyerId() {
            return lawyerId;
        }

        public void setLawyerId(Long lawyerId) {
            this.lawyerId = lawyerId;
        }

        public Long getAssigneeId() {
            return assigneeId;
        }

        public void setAssigneeId(Long assigneeId) {
            this.assigneeId = assigneeId;
        }

        public Long getPartnerAgencyId() {
            return partnerAgencyId;
        }

        public void setPartnerAgencyId(Long partnerAgencyId) {
            this.partnerAgencyId = partnerAgencyId;
        }

        public Instant getDateCreated() {
            return dateCreated;
        }

        public void setDateCreated(Instant dateCreated) {
            this.dateCreated = dateCreated;
        }
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
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

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void setUpdatedAt(Instant updatedAt) {
        this.updatedAt = updatedAt;
    }

    public List<WebhookSubscriptionItemResponseDto> getWebhooks() {
        return webhooks;
    }

    public void setWebhooks(List<WebhookSubscriptionItemResponseDto> webhooks) {
        this.webhooks = webhooks;
    }

    public List<CaseResponseDto> getCases() {
        return cases;
    }

    public void setCases(List<CaseResponseDto> cases) {
        this.cases = cases;
    }
}
