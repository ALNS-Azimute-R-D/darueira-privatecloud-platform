package de.legalhub.fakeagency.model;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "tb_received_webhook_event")
public class ReceivedWebhookEvent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "ds_agency_alias")
    private String partnerAgencyAlias;

    @Column(name = "partner_agency_id")
    private Long partnerAgencyId;

    @Column(name = "ds_event_type")
    private String eventType;

    @Column(name = "ds_delivery_id")
    private String deliveryId;

    @Column(name = "ds_signature")
    private String signature;

    @Column(name = "nr_timestamp")
    private Long timestamp;

    @Column(name = "st_signature_valid", nullable = false)
    private boolean signatureValid;

    @Lob
    @Column(name = "tx_payload", columnDefinition = "CLOB")
    private String payload;

    @Column(name = "ts_received_at")
    private Instant receivedAt = Instant.now();

    public ReceivedWebhookEvent() {}

    public ReceivedWebhookEvent(String partnerAgencyAlias, Long partnerAgencyId, String eventType,
                                String deliveryId, String signature, Long timestamp,
                                boolean signatureValid, String payload) {
        this.partnerAgencyAlias = partnerAgencyAlias;
        this.partnerAgencyId = partnerAgencyId;
        this.eventType = eventType;
        this.deliveryId = deliveryId;
        this.signature = signature;
        this.timestamp = timestamp;
        this.signatureValid = signatureValid;
        this.payload = payload;
        this.receivedAt = Instant.now();
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getPartnerAgencyAlias() { return partnerAgencyAlias; }
    public void setPartnerAgencyAlias(String partnerAgencyAlias) { this.partnerAgencyAlias = partnerAgencyAlias; }

    public Long getPartnerAgencyId() { return partnerAgencyId; }
    public void setPartnerAgencyId(Long partnerAgencyId) { this.partnerAgencyId = partnerAgencyId; }

    public String getEventType() { return eventType; }
    public void setEventType(String eventType) { this.eventType = eventType; }

    public String getDeliveryId() { return deliveryId; }
    public void setDeliveryId(String deliveryId) { this.deliveryId = deliveryId; }

    public String getSignature() { return signature; }
    public void setSignature(String signature) { this.signature = signature; }

    public Long getTimestamp() { return timestamp; }
    public void setTimestamp(Long timestamp) { this.timestamp = timestamp; }

    public boolean isSignatureValid() { return signatureValid; }
    public void setSignatureValid(boolean signatureValid) { this.signatureValid = signatureValid; }

    public String getPayload() { return payload; }
    public void setPayload(String payload) { this.payload = payload; }

    public Instant getReceivedAt() { return receivedAt; }
    public void setReceivedAt(Instant receivedAt) { this.receivedAt = receivedAt; }
}
