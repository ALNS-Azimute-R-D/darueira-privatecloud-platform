package de.legalhub.fakeagency.repository;

import de.legalhub.fakeagency.model.PartnerSubscriptionConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public interface PartnerSubscriptionConfigRepository extends JpaRepository<PartnerSubscriptionConfig, Long> {

    Optional<PartnerSubscriptionConfig> findByPartnerAgencyAlias(String partnerAgencyAlias);

    Optional<PartnerSubscriptionConfig> findByPartnerAgencyAliasIgnoreCase(String partnerAgencyAlias);

    Optional<PartnerSubscriptionConfig> findByPartnerAgencyId(Long partnerAgencyId);

    boolean existsByPartnerAgencyAlias(String partnerAgencyAlias);

    boolean existsByPartnerAgencyAliasIgnoreCase(String partnerAgencyAlias);
}
