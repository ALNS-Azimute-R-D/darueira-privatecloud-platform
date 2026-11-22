package de.legalhub.fakeagency.repository;

import de.legalhub.fakeagency.model.ReceivedWebhookEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ReceivedWebhookEventRepository extends JpaRepository<ReceivedWebhookEvent, Long> {

    List<ReceivedWebhookEvent> findByPartnerAgencyAliasOrderByReceivedAtDesc(String partnerAgencyAlias);

    List<ReceivedWebhookEvent> findByPartnerAgencyIdOrderByReceivedAtDesc(Long partnerAgencyId);
}
