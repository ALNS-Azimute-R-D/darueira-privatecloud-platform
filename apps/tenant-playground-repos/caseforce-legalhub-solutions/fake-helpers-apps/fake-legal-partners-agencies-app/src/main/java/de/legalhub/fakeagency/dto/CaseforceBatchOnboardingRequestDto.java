package de.legalhub.fakeagency.dto;

import java.util.List;

public class CaseforceBatchOnboardingRequestDto {

    private List<CaseforceOnboardingRequestDto> agencies;

    public CaseforceBatchOnboardingRequestDto() {}

    public CaseforceBatchOnboardingRequestDto(List<CaseforceOnboardingRequestDto> agencies) {
        this.agencies = agencies;
    }

    public List<CaseforceOnboardingRequestDto> getAgencies() {
        return agencies;
    }

    public void setAgencies(List<CaseforceOnboardingRequestDto> agencies) {
        this.agencies = agencies;
    }
}
