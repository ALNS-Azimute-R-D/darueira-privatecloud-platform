package de.legalhub.fakeagency.model;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "tb_partner_subscription_config")
public class PartnerSubscriptionConfig {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "ds_agency_alias", nullable = false, unique = true)
    private String partnerAgencyAlias;

    @Column(name = "partner_agency_id")
    private Long partnerAgencyId;

    @Column(name = "ds_agency_name")
    private String agencyName;

    @Column(name = "ds_agency_email")
    private String agencyEmail;

    @Column(name = "ds_secret", nullable = false)
    private String secret;

    @Column(name = "ds_target_url", nullable = false)
    private String targetUrl;

    @Column(name = "nm_caseforce_subscription_id")
    private Long caseforceSubscriptionId;

    @Column(name = "ts_date_created")
    private Instant dateCreated = Instant.now();

    @Column(name = "ts_date_updated")
    private Instant dateUpdated = Instant.now();

    public PartnerSubscriptionConfig() {}

    public PartnerSubscriptionConfig(String partnerAgencyAlias, Long partnerAgencyId, String agencyName,
                                   String agencyEmail, String secret, String targetUrl) {
        this.partnerAgencyAlias = partnerAgencyAlias;
        this.partnerAgencyId = partnerAgencyId;
        this.agencyName = agencyName;
        this.agencyEmail = agencyEmail;
        this.secret = secret;
        this.targetUrl = targetUrl;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getPartnerAgencyAlias() { return partnerAgencyAlias; }
    public void setPartnerAgencyAlias(String partnerAgencyAlias) { this.partnerAgencyAlias = partnerAgencyAlias; }

    public Long getPartnerAgencyId() { return partnerAgencyId; }
    public void setPartnerAgencyId(Long partnerAgencyId) { this.partnerAgencyId = partnerAgencyId; }

    public String getAgencyName() { return agencyName; }
    public void setAgencyName(String agencyName) { this.agencyName = agencyName; }

    public String getAgencyEmail() { return agencyEmail; }
    public void setAgencyEmail(String agencyEmail) { this.agencyEmail = agencyEmail; }

    public String getSecret() { return secret; }
    public void setSecret(String secret) { this.secret = secret; }

    public String getTargetUrl() { return targetUrl; }
    public void setTargetUrl(String targetUrl) { this.targetUrl = targetUrl; }

    public Long getCaseforceSubscriptionId() { return caseforceSubscriptionId; }
    public void setCaseforceSubscriptionId(Long caseforceSubscriptionId) { this.caseforceSubscriptionId = caseforceSubscriptionId; }

    public Instant getDateCreated() { return dateCreated; }
    public void setDateCreated(Instant dateCreated) { this.dateCreated = dateCreated; }

    public Instant getDateUpdated() { return dateUpdated; }
    public void setDateUpdated(Instant dateUpdated) { this.dateUpdated = dateUpdated; }
}
