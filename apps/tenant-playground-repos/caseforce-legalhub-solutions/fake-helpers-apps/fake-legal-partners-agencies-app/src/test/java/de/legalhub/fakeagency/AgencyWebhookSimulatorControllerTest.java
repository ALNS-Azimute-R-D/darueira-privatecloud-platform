package de.legalhub.fakeagency;

import com.fasterxml.jackson.databind.ObjectMapper;
import de.legalhub.fakeagency.dto.CaseforceOnboardingResponseDto;
import de.legalhub.fakeagency.model.PartnerSubscriptionConfig;
import de.legalhub.fakeagency.model.ReceivedWebhookEvent;
import de.legalhub.fakeagency.repository.PartnerSubscriptionConfigRepository;
import de.legalhub.fakeagency.repository.ReceivedWebhookEventRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.ClientHttpRequest;
import org.springframework.http.client.ClientHttpRequestFactory;
import org.springframework.http.client.ClientHttpResponse;
import org.springframework.mock.http.client.MockClientHttpRequest;
import org.springframework.mock.http.client.MockClientHttpResponse;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.client.RestClient;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
public class AgencyWebhookSimulatorControllerTest {

    private static final AtomicBoolean simulateCaseforceError = new AtomicBoolean(false);

    @TestConfiguration
    static class MockCaseforceTestConfig {
        @Bean
        @Primary
        public RestClient caseforceRestClient(ObjectMapper objectMapper) {
            return RestClient.builder()
                    .requestFactory(new ClientHttpRequestFactory() {
                        @Override
                        public ClientHttpRequest createRequest(URI uri, HttpMethod httpMethod) {
                            return new MockClientHttpRequest(httpMethod, uri) {
                                @Override
                                protected ClientHttpResponse executeInternal() {
                                    if (simulateCaseforceError.get()) {
                                        byte[] errorBody = "{\"_embedded\":{\"errors\":[{\"message\":\"Forbidden\"}]},\"message\":\"Forbidden\"}".getBytes(StandardCharsets.UTF_8);
                                        MockClientHttpResponse response = new MockClientHttpResponse(errorBody, HttpStatus.FORBIDDEN);
                                        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
                                        return response;
                                    }

                                    CaseforceOnboardingResponseDto.WebhookSubscriptionItemResponseDto sub =
                                            new CaseforceOnboardingResponseDto.WebhookSubscriptionItemResponseDto();
                                    sub.setId(501L);
                                    sub.setPartnerAgencyId(101L);
                                    sub.setTargetUrl(uri.toString());
                                    sub.setStatus("ACTIVE");
                                    sub.setEventTypes(List.of("LEGAL_CASE_CREATED"));

                                    CaseforceOnboardingResponseDto resp = new CaseforceOnboardingResponseDto();
                                    resp.setId(101L);
                                    resp.setAlias("mock-agency");
                                    resp.setName("Mock Agency");
                                    resp.setStatus("ACTIVE");
                                    resp.setWebhooks(List.of(sub));

                                    try {
                                        byte[] body = objectMapper.writeValueAsBytes(resp);
                                        MockClientHttpResponse response = new MockClientHttpResponse(body, HttpStatus.CREATED);
                                        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);
                                        return response;
                                    } catch (Exception e) {
                                        throw new RuntimeException(e);
                                    }
                                }
                            };
                        }
                    })
                    .build();
        }
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private PartnerSubscriptionConfigRepository configRepository;

    @Autowired
    private ReceivedWebhookEventRepository eventRepository;

    @BeforeEach
    void setUp() {
        simulateCaseforceError.set(false);
        eventRepository.deleteAll();
        configRepository.deleteAll();
    }

    @Test
    void shouldOnboardAndRetrieveAgencyByAlias() throws Exception {
        mockMvc.perform(post("/api/agencies/onboard")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "alias": "berlin-legal",
                                  "name": "Berlin Legal Partner",
                                  "email": "contact@berlin-legal.de",
                                  "secret": "test_secret_101",
                                  "eventTypes": ["LEGAL_CASE_CREATED", "LEGAL_CASE_UPDATED"]
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.partnerAgencyAlias").value("berlin-legal"))
                .andExpect(jsonPath("$.agencyName").value("Berlin Legal Partner"))
                .andExpect(jsonPath("$.partnerAgencyId").value(101))
                .andExpect(jsonPath("$.caseforceSubscriptionId").value(501))
                .andExpect(jsonPath("$.targetUrl").value("http://localhost:8085/api/agencies/berlin-legal/webhooks/caseforce"));

        mockMvc.perform(get("/api/agencies/berlin-legal/config"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.partnerAgencyAlias").value("berlin-legal"))
                .andExpect(jsonPath("$.partnerAgencyId").value(101))
                .andExpect(jsonPath("$.secret").value("test_secret_101"));
    }

    @Test
    void shouldRollbackAndReturnForbiddenWhenCaseforceRejectsOnboarding() throws Exception {
        simulateCaseforceError.set(true);

        mockMvc.perform(post("/api/agencies/onboard")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "alias": "rejected-agency",
                                  "name": "Rejected Agency",
                                  "email": "rejected@agency.de"
                                }
                                """))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value("CaseForce LegalHub Integration Failure"))
                .andExpect(jsonPath("$.status").value(403))
                .andExpect(jsonPath("$.message").exists());

        // Verify transactional rollback in H2: no config was saved
        assertThat(configRepository.findByPartnerAgencyAlias("rejected-agency")).isEmpty();
    }

    @Test
    void shouldReceiveAndValidateWebhookWithHmacSignatureByAlias() throws Exception {
        String alias = "munich-law";
        String secret = "signing_secret_202";
        configRepository.save(new PartnerSubscriptionConfig(alias, 202L, "Munich Agency", "info@munich-law.de", secret, "http://localhost:8085/api/agencies/munich-law/webhooks/caseforce"));

        String payload = "{\"eventType\":\"LEGAL_CASE_UPDATED\",\"caseNumber\":\"CASE-777\"}";
        long timestamp = 1724580000000L;
        String signature = computeHmac(payload, timestamp, secret);

        mockMvc.perform(post("/api/agencies/munich-law/webhooks/caseforce")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("X-Caseforce-Signature-256", signature)
                        .header("X-Caseforce-Timestamp", timestamp)
                        .header("X-Caseforce-Delivery-Id", "del-12345")
                        .header("X-Caseforce-Event", "LEGAL_CASE_UPDATED")
                        .content(payload))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.partnerAgencyAlias").value("munich-law"))
                .andExpect(jsonPath("$.partnerAgencyId").value(202))
                .andExpect(jsonPath("$.signatureValid").value(true))
                .andExpect(jsonPath("$.deliveryId").value("del-12345"));

        List<ReceivedWebhookEvent> events = eventRepository.findByPartnerAgencyAliasOrderByReceivedAtDesc("munich-law");
        assertThat(events).hasSize(1);
        assertThat(events.get(0).isSignatureValid()).isTrue();
    }

    @Test
    void shouldIsolateEventsBetweenDifferentAgencies() throws Exception {
        configRepository.save(new PartnerSubscriptionConfig("agency-one", 1L, "Agency One", "a1@test.de", "sec1", "url1"));
        configRepository.save(new PartnerSubscriptionConfig("agency-two", 2L, "Agency Two", "a2@test.de", "sec2", "url2"));

        eventRepository.save(new ReceivedWebhookEvent("agency-one", 1L, "CASE_EVENT", "d1", "sig", 1000L, true, "{}"));
        eventRepository.save(new ReceivedWebhookEvent("agency-one", 1L, "CASE_EVENT", "d2", "sig", 2000L, true, "{}"));
        eventRepository.save(new ReceivedWebhookEvent("agency-two", 2L, "CASE_EVENT", "d3", "sig", 3000L, true, "{}"));

        mockMvc.perform(get("/api/agencies/agency-one/webhooks/events"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2));

        mockMvc.perform(get("/api/agencies/agency-two/webhooks/events"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1));
    }

    @Test
    void shouldOnboardAgencyWithEnrichedPayloadIncludingCasesAndActions() throws Exception {
        mockMvc.perform(post("/api/agencies/onboard")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "alias": "hamburg-legal",
                                  "name": "Hamburg Legal Group",
                                  "email": "contact@hamburg-legal.de",
                                  "secret": "hamburg_sec_999",
                                  "eventTypes": ["LEGAL_CASE_CREATED"],
                                  "cases": [
                                    {
                                      "caseNumber": "CASE-HAM-101",
                                      "legalField": "Labor Law",
                                      "status": "OPEN",
                                      "summary": "Employment contract dispute",
                                      "lawyer": {
                                        "email": "lawyer.huber@hamburg-legal.de",
                                        "firstname": "Klaus",
                                        "lastname": "Huber"
                                      },
                                      "assignee": {
                                        "email": "assignee.bauer@hamburg-legal.de",
                                        "firstname": "Sarah",
                                        "lastname": "Bauer"
                                      },
                                      "actions": [
                                        {
                                          "name": "Review contract clauses",
                                          "isTask": true,
                                          "status": "OPEN",
                                          "assignee": {
                                            "email": "clerk.meyer@hamburg-legal.de",
                                            "firstname": "Max",
                                            "lastname": "Meyer"
                                          },
                                          "dueDate": "2026-12-31",
                                          "notes": "Urgent review"
                                        }
                                      ]
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.partnerAgencyAlias").value("hamburg-legal"))
                .andExpect(jsonPath("$.partnerAgencyId").value(101))
                .andExpect(jsonPath("$.agencyName").value("Hamburg Legal Group"));

        assertThat(configRepository.findByPartnerAgencyAlias("hamburg-legal")).isPresent();
    }

    @Test
    void shouldBatchOnboardMultipleAgencies() throws Exception {
        mockMvc.perform(post("/api/agencies/batch-onboard")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "agencies": [
                                    {
                                      "alias": "stuttgart-law",
                                      "name": "Stuttgart Law Partners",
                                      "email": "info@stuttgart-law.de"
                                    },
                                    {
                                      "alias": "dresden-law",
                                      "name": "Dresden Advocates",
                                      "email": "info@dresden-law.de"
                                    }
                                  ]
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].partnerAgencyAlias").value("stuttgart-law"))
                .andExpect(jsonPath("$[0].partnerAgencyId").value(101))
                .andExpect(jsonPath("$[1].partnerAgencyAlias").value("dresden-law"))
                .andExpect(jsonPath("$[1].partnerAgencyId").value(101));

        assertThat(configRepository.findByPartnerAgencyAlias("stuttgart-law")).isPresent();
        assertThat(configRepository.findByPartnerAgencyAlias("dresden-law")).isPresent();
    }

    private String computeHmac(String payload, long timestamp, String secret) {
        try {
            String toSign = timestamp + "." + payload;
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] rawHmac = mac.doFinal(toSign.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : rawHmac) {
                sb.append(String.format("%02x", b));
            }
            return "sha256=" + sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
