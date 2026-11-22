package de.legalhub.fakeagency.service;

import de.legalhub.fakeagency.dto.*;
import de.legalhub.fakeagency.exception.CaseforceIntegrationException;
import de.legalhub.fakeagency.model.PartnerSubscriptionConfig;
import de.legalhub.fakeagency.model.ReceivedWebhookEvent;
import de.legalhub.fakeagency.repository.PartnerSubscriptionConfigRepository;
import de.legalhub.fakeagency.repository.ReceivedWebhookEventRepository;
import de.legalhub.fakeagency.security.HmacSignatureVerifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.*;
import java.util.function.Supplier;

@Service
public class AgencySimulatorService {

    private static final Logger log = LoggerFactory.getLogger(AgencySimulatorService.class);

    private final PartnerSubscriptionConfigRepository configRepository;
    private final ReceivedWebhookEventRepository eventRepository;
    private final HmacSignatureVerifier signatureVerifier;
    private final RestClient caseforceRestClient;
    private final CaseforceAuthTokenService tokenService;

    @Value("${caseforce.api.webhook-callback-host:http://localhost:8085}")
    private String webhookCallbackHost;

    @Value("${caseforce.api.base-url:http://localhost:8080}")
    private String caseforceBaseUrl;

    public AgencySimulatorService(PartnerSubscriptionConfigRepository configRepository,
                                  ReceivedWebhookEventRepository eventRepository,
                                  HmacSignatureVerifier signatureVerifier,
                                  RestClient caseforceRestClient,
                                  CaseforceAuthTokenService tokenService) {
        this.configRepository = configRepository;
        this.eventRepository = eventRepository;
        this.signatureVerifier = signatureVerifier;
        this.caseforceRestClient = caseforceRestClient;
        this.tokenService = tokenService;
    }

    public Optional<PartnerSubscriptionConfig> getConfigByAlias(String partnerAgencyAlias) {
        if (partnerAgencyAlias == null || partnerAgencyAlias.isBlank()) {
            return Optional.empty();
        }
        String clean = partnerAgencyAlias.trim();
        return configRepository.findByPartnerAgencyAliasIgnoreCase(clean)
                .or(() -> {
                    try {
                        Long numericId = Long.parseLong(clean);
                        return configRepository.findByPartnerAgencyId(numericId);
                    } catch (NumberFormatException e) {
                        return Optional.empty();
                    }
                });
    }

    public Optional<PartnerSubscriptionConfig> getConfigById(Long partnerAgencyId) {
        return configRepository.findByPartnerAgencyId(partnerAgencyId);
    }

    public List<PartnerSubscriptionConfig> getAllConfigs() {
        return configRepository.findAll();
    }

    public List<ReceivedWebhookEvent> getEventsByAlias(String partnerAgencyAlias) {
        if (partnerAgencyAlias == null || partnerAgencyAlias.isBlank()) {
            return Collections.emptyList();
        }
        return eventRepository.findByPartnerAgencyAliasOrderByReceivedAtDesc(partnerAgencyAlias.trim().toLowerCase());
    }

    public List<ReceivedWebhookEvent> getEventsById(Long partnerAgencyId) {
        return eventRepository.findByPartnerAgencyIdOrderByReceivedAtDesc(partnerAgencyId);
    }

    public List<ReceivedWebhookEvent> getAllEvents() {
        return eventRepository.findAll();
    }

    @Transactional
    public PartnerSubscriptionConfig onboardAgency(PartnerAgencyRequestDto requestDto) {
        String rawAlias = requestDto != null ? requestDto.getAlias() : null;
        String normalizedAlias = (rawAlias != null && !rawAlias.isBlank())
                ? rawAlias.trim().toLowerCase()
                : "agency-" + UUID.randomUUID().toString().substring(0, 8);

        String rawName = requestDto != null ? requestDto.getName() : null;
        String effectiveName = (rawName != null && !rawName.isBlank()) ? rawName.trim() : normalizedAlias;

        String rawEmail = requestDto != null ? requestDto.getEmail() : null;
        String effectiveEmail = (rawEmail != null && !rawEmail.isBlank()) ? rawEmail.trim() : null;

        String targetUrl = webhookCallbackHost + "/api/agencies/" + normalizedAlias + "/webhooks/caseforce";

        String rawSecret = requestDto != null ? requestDto.getSecret() : null;
        String effectiveSecret = (rawSecret != null && !rawSecret.isBlank()) ? rawSecret.trim() : generateSecret();

        List<String> rawEvents = requestDto != null ? requestDto.getEventTypes() : null;
        List<String> effectiveEvents = (rawEvents != null && !rawEvents.isEmpty())
                ? rawEvents
                : List.of("LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED", "ACTION_CREATED", "ACTION_UPDATED");

        // Pre-save local config so that webhooks fired synchronously/asynchronously during onboarding can immediately resolve this agency and verify signatures
        PartnerSubscriptionConfig config = configRepository.findByPartnerAgencyAliasIgnoreCase(normalizedAlias)
                .orElse(new PartnerSubscriptionConfig(normalizedAlias, null, effectiveName, effectiveEmail, effectiveSecret, targetUrl));

        config.setPartnerAgencyAlias(normalizedAlias);
        config.setAgencyName(effectiveName);
        config.setAgencyEmail(effectiveEmail);
        config.setSecret(effectiveSecret);
        config.setTargetUrl(targetUrl);
        config.setDateUpdated(Instant.now());
        config = configRepository.saveAndFlush(config);

        // Prepare strongly-typed DTOs for CaseForce LegalHub Onboarding API
        CaseforceOnboardingRequestDto.WebhookItemDto webhookItem =
                new CaseforceOnboardingRequestDto.WebhookItemDto(targetUrl, effectiveSecret, effectiveEvents);

        List<CaseforceOnboardingRequestDto.CaseItemDto> caseDtos = null;
        if (requestDto != null && requestDto.getLegalCases() != null) {
            caseDtos = requestDto.getLegalCases().stream().map(c -> {
                CaseforceOnboardingRequestDto.UserItemDto lawyer = mapUser(c.getLawyer());
                CaseforceOnboardingRequestDto.UserItemDto assignee = mapUser(c.getAssignee());
                List<CaseforceOnboardingRequestDto.ActionItemDto> actions = null;
                if (c.getActions() != null) {
                    actions = c.getActions().stream().map(a -> new CaseforceOnboardingRequestDto.ActionItemDto(
                            a.getName(),
                            a.isTask(),
                            a.getStatus(),
                            mapUser(a.getAssignee()),
                            a.getDueDate(),
                            a.getNotes()
                    )).toList();
                }
                return new CaseforceOnboardingRequestDto.CaseItemDto(
                        c.getCaseNumber(),
                        c.getLegalField(),
                        c.getStatus(),
                        c.getSummary(),
                        lawyer,
                        assignee,
                        actions
                );
            }).toList();
        }

        CaseforceOnboardingRequestDto onboardingRequest = new CaseforceOnboardingRequestDto(
                effectiveName,
                normalizedAlias,
                effectiveEmail,
                "ACTIVE",
                List.of(webhookItem),
                caseDtos
        );

        String targetOnboardingUri = (caseforceBaseUrl != null ? caseforceBaseUrl.replaceAll("/+$", "") : "http://localhost:8080")
                + "/partner-agencies/onboarding";
        log.info("Sending onboarding request to CaseForce LegalHub at '{}' for partner agency '{}' with {} cases",
                targetOnboardingUri, normalizedAlias, caseDtos != null ? caseDtos.size() : 0);

        // Execute API call with automatic 401/403 token re-authentication and retry
        CaseforceOnboardingResponseDto response;
        try {
            response = executeWithAuthRetry(() -> caseforceRestClient.post()
                    .uri(targetOnboardingUri)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(onboardingRequest)
                    .retrieve()
                    .body(CaseforceOnboardingResponseDto.class)
            );
        } catch (Exception ex) {
            // Clean up pre-saved config on failure and re-throw
            configRepository.delete(config);
            configRepository.flush();
            throw ex;
        }

        if (response == null) {
            configRepository.delete(config);
            configRepository.flush();
            throw new CaseforceIntegrationException("Received empty response from CaseForce LegalHub for partner agency: " + normalizedAlias, null);
        }

        // Enrich and update config with CaseForce generated IDs and subscription
        if (response.getId() != null) {
            config.setPartnerAgencyId(response.getId());
        }
        if (response.getWebhooks() != null && !response.getWebhooks().isEmpty()) {
            CaseforceOnboardingResponseDto.WebhookSubscriptionItemResponseDto firstSub = response.getWebhooks().get(0);
            if (firstSub.getId() != null) {
                config.setCaseforceSubscriptionId(firstSub.getId());
            }
            if (firstSub.getSecret() != null && !firstSub.getSecret().isBlank()) {
                config.setSecret(firstSub.getSecret());
            }
        }
        config.setDateUpdated(Instant.now());

        log.info("Successfully onboarded Partner Agency '{}' on CaseForce LegalHub: AgencyID={}, SubID={}, CasesCreated={}",
                normalizedAlias, config.getPartnerAgencyId(), config.getCaseforceSubscriptionId(),
                response.getCases() != null ? response.getCases().size() : 0);

        return configRepository.save(config);
    }

    @Transactional
    public PartnerSubscriptionConfig onboardAgency(String partnerAgencyAlias, PartnerAgencyRequestDto requestDto) {
        PartnerAgencyRequestDto effectiveDto = requestDto != null ? requestDto : new PartnerAgencyRequestDto();
        effectiveDto.setAlias(partnerAgencyAlias);
        if (effectiveDto.getName() == null || effectiveDto.getName().isBlank()) {
            effectiveDto.setName(partnerAgencyAlias);
        }
        return onboardAgency(effectiveDto);
    }

    @Transactional
    public List<PartnerSubscriptionConfig> onboardBatchAgencies(PartnerAgencyBatchRequestDto batchRequestDto) {
        if (batchRequestDto == null || batchRequestDto.getAgencies() == null) {
            return Collections.emptyList();
        }
        List<PartnerSubscriptionConfig> results = new ArrayList<>();
        for (PartnerAgencyRequestDto agencyDto : batchRequestDto.getAgencies()) {
            results.add(onboardAgency(agencyDto));
        }
        return results;
    }

    private <T> T executeWithAuthRetry(Supplier<T> apiCall) {
        try {
            return apiCall.get();
        } catch (RestClientResponseException e) {
            if (e.getStatusCode().value() == 401 || e.getStatusCode().value() == 403) {
                log.warn("Encountered status {} from CaseForce LegalHub. Invalidating JWT and retrying request once...", e.getStatusCode());
                tokenService.invalidateToken();
                try {
                    return apiCall.get();
                } catch (RestClientResponseException retryEx) {
                    String responseBody = retryEx.getResponseBodyAsString();
                    log.error("CaseForce LegalHub request failed on retry with status {}: {}", retryEx.getStatusCode(), responseBody);
                    throw new CaseforceIntegrationException(
                            "CaseForce LegalHub rejected request: " + retryEx.getStatusCode() + " - " + responseBody,
                            retryEx.getStatusCode(),
                            responseBody,
                            retryEx
                    );
                } catch (Exception retryEx) {
                    log.error("Failed to communicate with CaseForce LegalHub on retry: {}", retryEx.getMessage(), retryEx);
                    throw new CaseforceIntegrationException("Failed to communicate with CaseForce LegalHub: " + retryEx.getMessage(), retryEx);
                }
            }
            String responseBody = e.getResponseBodyAsString();
            log.error("CaseForce LegalHub request failed with status {}: {}", e.getStatusCode(), responseBody);
            throw new CaseforceIntegrationException(
                    "CaseForce LegalHub rejected request: " + e.getStatusCode() + " - " + responseBody,
                    e.getStatusCode(),
                    responseBody,
                    e
            );
        } catch (Exception e) {
            log.error("Failed to communicate with CaseForce LegalHub: {}", e.getMessage(), e);
            throw new CaseforceIntegrationException("Failed to communicate with CaseForce LegalHub: " + e.getMessage(), e);
        }
    }

    private CaseforceOnboardingRequestDto.UserItemDto mapUser(UserDto userDto) {
        if (userDto == null) return null;
        return new CaseforceOnboardingRequestDto.UserItemDto(
                userDto.getEmail(),
                userDto.getFirstname(),
                userDto.getLastname(),
                userDto.getPassword(),
                userDto.isEnabled(),
                userDto.getRoles()
        );
    }

    @Transactional
    public ReceivedWebhookEvent processIncomingWebhook(IncomingWebhookRequestDto webhookRequest) {
        String agencyIdentifier = webhookRequest != null && webhookRequest.getAgencyIdentifier() != null
                ? webhookRequest.getAgencyIdentifier().trim()
                : "unknown";

        Optional<PartnerSubscriptionConfig> configOpt = getConfigByAlias(agencyIdentifier);

        boolean isValid = false;
        String alias = agencyIdentifier;
        Long agencyId = null;

        Long timestamp = (webhookRequest != null && webhookRequest.getTimestamp() != null)
                ? webhookRequest.getTimestamp()
                : System.currentTimeMillis();

        String rawPayload = webhookRequest != null ? webhookRequest.getRawPayload() : null;
        String signatureHeader = webhookRequest != null ? webhookRequest.getSignatureHeader() : null;
        String eventType = (webhookRequest != null && webhookRequest.getEventType() != null)
                ? webhookRequest.getEventType()
                : "UNKNOWN";
        String deliveryId = (webhookRequest != null && webhookRequest.getDeliveryId() != null)
                ? webhookRequest.getDeliveryId()
                : "N/A";

        if (configOpt.isPresent()) {
            PartnerSubscriptionConfig config = configOpt.get();
            alias = config.getPartnerAgencyAlias();
            agencyId = config.getPartnerAgencyId();
            isValid = signatureVerifier.verify(rawPayload, timestamp, config.getSecret(), signatureHeader);
            log.info("Processed webhook for agency '{}' (ID={}): Event={}, SignatureValid={}",
                    alias, agencyId, eventType, isValid);
        } else {
            log.warn("Received webhook for unknown agency identifier '{}'. Verification skipped (FALSE).", agencyIdentifier);
        }

        ReceivedWebhookEvent event = new ReceivedWebhookEvent(
                alias,
                agencyId,
                eventType,
                deliveryId,
                signatureHeader != null ? signatureHeader : "N/A",
                timestamp,
                isValid,
                rawPayload
        );

        return eventRepository.save(event);
    }

    private String generateSecret() {
        byte[] randomBytes = new byte[24];
        new SecureRandom().nextBytes(randomBytes);
        return "whsec_" + Base64.getUrlEncoder().withoutPadding().encodeToString(randomBytes);
    }
}
