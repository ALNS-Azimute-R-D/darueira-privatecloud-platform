package de.legalhub.fakeagency.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;

import java.util.List;

@Schema(description = "Batch onboarding request payload for multiple Partner Agencies")
public class PartnerAgencyBatchRequestDto {

    @Valid
    @Schema(description = "Collection of partner agencies to onboard in batch")
    private List<PartnerAgencyRequestDto> agencies;

    public PartnerAgencyBatchRequestDto() {}

    public PartnerAgencyBatchRequestDto(List<PartnerAgencyRequestDto> agencies) {
        this.agencies = agencies;
    }

    public List<PartnerAgencyRequestDto> getAgencies() {
        return agencies;
    }

    public void setAgencies(List<PartnerAgencyRequestDto> agencies) {
        this.agencies = agencies;
    }
}
