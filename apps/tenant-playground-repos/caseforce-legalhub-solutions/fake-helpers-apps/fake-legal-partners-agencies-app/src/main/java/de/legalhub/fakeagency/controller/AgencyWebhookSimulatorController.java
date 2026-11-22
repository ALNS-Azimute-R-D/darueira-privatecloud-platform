package de.legalhub.fakeagency.controller;

import de.legalhub.fakeagency.dto.IncomingWebhookRequestDto;
import de.legalhub.fakeagency.dto.PartnerAgencyBatchRequestDto;
import de.legalhub.fakeagency.dto.PartnerAgencyRequestDto;
import de.legalhub.fakeagency.model.PartnerSubscriptionConfig;
import de.legalhub.fakeagency.model.ReceivedWebhookEvent;
import de.legalhub.fakeagency.service.AgencySimulatorService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/agencies")
@Tag(name = "Agency Webhooks & Multi-Partner Simulation", description = "Multi-Agency Legal Partner simulation endpoints for registering fake agencies on CaseForce and consuming webhooks")
public class AgencyWebhookSimulatorController {

    private final AgencySimulatorService simulatorService;

    public AgencyWebhookSimulatorController(AgencySimulatorService simulatorService) {
        this.simulatorService = simulatorService;
    }

    /**
     * Onboards a fake partner agency with webhooks pointing to this simulator.
     */
    @PostMapping("/onboard")
    @Operation(
            summary = "Onboard Fake Partner Agency",
            description = "Registers a new Partner Agency on CaseForce LegalHub and provisions its webhook to point back to this simulator app."
    )
    @ApiResponses({
            @ApiResponse(responseCode = "201", description = "Partner agency onboarded successfully in simulator and CaseForce",
                    content = @Content(schema = @Schema(implementation = PartnerSubscriptionConfig.class)))
    })
    public ResponseEntity<PartnerSubscriptionConfig> onboard(
            @Valid @RequestBody PartnerAgencyRequestDto request
    ) {
        PartnerSubscriptionConfig config = simulatorService.onboardAgency(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(config);
    }

    /**
     * Onboards a batch collection of fake partner agencies.
     */
    @PostMapping("/batch-onboard")
    @Operation(
            summary = "Batch Onboard Fake Partner Agencies",
            description = "Registers a batch collection of Partner Agencies on CaseForce LegalHub with webhooks and cases."
    )
    @ApiResponses({
            @ApiResponse(responseCode = "201", description = "Partner agencies batch onboarded successfully",
                    content = @Content(schema = @Schema(implementation = PartnerSubscriptionConfig.class)))
    })
    public ResponseEntity<List<PartnerSubscriptionConfig>> batchOnboard(
            @Valid @RequestBody PartnerAgencyBatchRequestDto request
    ) {
        List<PartnerSubscriptionConfig> configs = simulatorService.onboardBatchAgencies(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(configs);
    }

    /**
     * Onboard/configure a partner agency specified by alias in the path.
     */
    @PostMapping("/{partnerAgencyAlias}/onboard")
    @Operation(
            summary = "Onboard Fake Agency by Alias",
            description = "Registers or updates a specific partner agency by alias, provisioning webhooks to this simulator."
    )
    @ApiResponses({
            @ApiResponse(responseCode = "201", description = "Partner agency configured successfully",
                    content = @Content(schema = @Schema(implementation = PartnerSubscriptionConfig.class)))
    })
    public ResponseEntity<PartnerSubscriptionConfig> onboardByPath(
            @Parameter(description = "Unique alphanumeric alias identifier for the agency", example = "berlin-legal-partners")
            @PathVariable("partnerAgencyAlias") String partnerAgencyAlias,
            @Valid @RequestBody(required = false) PartnerAgencyRequestDto request
    ) {
        PartnerSubscriptionConfig config = simulatorService.onboardAgency(partnerAgencyAlias, request);
        return ResponseEntity.status(HttpStatus.CREATED).body(config);
    }

    /**
     * Webhook receiver endpoint called by CaseForce LegalHub.
     */
    @PostMapping("/{partnerAgencyAlias}/webhooks/caseforce")
    @Operation(
            summary = "Receive CaseForce Webhook",
            description = "Callback endpoint called by CaseForce LegalHub for this agency. Verifies HMAC-SHA256 signature and records the event in H2."
    )
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "Webhook event received, signature validated, and recorded",
                    content = @Content(schema = @Schema(implementation = ReceivedWebhookEvent.class)))
    })
    public ResponseEntity<ReceivedWebhookEvent> receiveWebhook(
            @Parameter(description = "Alias identifier of the Partner Agency receiving this webhook", example = "berlin-legal-partners")
            @PathVariable("partnerAgencyAlias") String partnerAgencyAlias,
            @Parameter(description = "HMAC-SHA256 signature header", example = "sha256=1a2b3c4d...")
            @RequestHeader(value = "X-Caseforce-Signature-256", required = false) String signature,
            @Parameter(description = "Unix timestamp millisecond when payload was signed", example = "1724580000000")
            @RequestHeader(value = "X-Caseforce-Timestamp", required = false) Long timestamp,
            @Parameter(description = "Unique delivery ID from CaseForce", example = "del-12345")
            @RequestHeader(value = "X-Caseforce-Delivery-Id", required = false) String deliveryId,
            @Parameter(description = "Event type name", example = "LEGAL_CASE_UPDATED")
            @RequestHeader(value = "X-Caseforce-Event", required = false) String eventType,
            @RequestBody String rawPayload
    ) {
        IncomingWebhookRequestDto webhookRequest = new IncomingWebhookRequestDto(
                partnerAgencyAlias,
                signature,
                timestamp != null ? timestamp : System.currentTimeMillis(),
                deliveryId,
                eventType != null ? eventType : "UNKNOWN",
                rawPayload
        );
        ReceivedWebhookEvent event = simulatorService.processIncomingWebhook(webhookRequest);
        return ResponseEntity.ok(event);
    }

    /**
     * Lists all received webhook events for this specific partner agency.
     */
    @GetMapping("/{partnerAgencyAlias}/webhooks/events")
    @Operation(summary = "List Received Webhook Events", description = "Retrieves the audit log of all webhooks received for this specific agency.")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "List of received webhook events")
    })
    public ResponseEntity<List<ReceivedWebhookEvent>> getReceivedEvents(
            @Parameter(description = "Alias identifier of the Partner Agency", example = "berlin-legal-partners")
            @PathVariable("partnerAgencyAlias") String partnerAgencyAlias
    ) {
        return ResponseEntity.ok(simulatorService.getEventsByAlias(partnerAgencyAlias));
    }

    /**
     * Retrieves the current configuration/subscription for this specific partner agency.
     */
    @GetMapping("/{partnerAgencyAlias}/config")
    @Operation(summary = "Get Partner Agency Configuration", description = "Retrieves stored target URL, secret, and subscription ID for this agency.")
    @ApiResponses({
            @ApiResponse(responseCode = "200", description = "Configuration found",
                    content = @Content(schema = @Schema(implementation = PartnerSubscriptionConfig.class))),
            @ApiResponse(responseCode = "404", description = "Configuration not found")
    })
    public ResponseEntity<PartnerSubscriptionConfig> getConfig(
            @Parameter(description = "Alias identifier of the Partner Agency", example = "berlin-legal-partners")
            @PathVariable("partnerAgencyAlias") String partnerAgencyAlias
    ) {
        return simulatorService.getConfigByAlias(partnerAgencyAlias)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * Lists all onboarded fake partner agencies.
     */
    @GetMapping
    @Operation(summary = "List All Fake Partner Agencies", description = "Lists all partner agencies registered in the simulator.")
    public ResponseEntity<List<PartnerSubscriptionConfig>> listAgencies() {
        return ResponseEntity.ok(simulatorService.getAllConfigs());
    }

    /**
     * Lists all received events across all partner agencies.
     */
    @GetMapping("/events")
    @Operation(summary = "List All Received Events", description = "Retrieves audit log of all webhooks received across all simulated agencies.")
    public ResponseEntity<List<ReceivedWebhookEvent>> listAllEvents() {
        return ResponseEntity.ok(simulatorService.getAllEvents());
    }
}
