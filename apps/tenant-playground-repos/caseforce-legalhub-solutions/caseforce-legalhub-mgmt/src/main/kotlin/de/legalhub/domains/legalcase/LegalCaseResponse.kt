package de.legalhub.domains.legalcase

import de.legalhub.model.LegalCase
import io.micronaut.serde.annotation.Serdeable
import java.time.Instant

@Serdeable
data class LegalCaseResponse(
    val id: Long,
    val caseNumber: String?,
    val legalField: String?,
    val status: String,
    val summary: String?,
    val lawyerId: Long?,
    val assigneeId: Long?,
    val partnerAgencyId: Long?,
    val dateCreated: Instant?,
) {
    companion object {
        fun from(legalCase: LegalCase) = LegalCaseResponse(
            id = legalCase.id!!,
            caseNumber = legalCase.caseNumber,
            legalField = legalCase.legalField,
            status = legalCase.status.name,
            summary = legalCase.summary,
            lawyerId = legalCase.lawyer?.id,
            assigneeId = legalCase.assignee?.id,
            partnerAgencyId = legalCase.partnerAgency?.id,
            dateCreated = legalCase.createdAt,
        )
    }
}
