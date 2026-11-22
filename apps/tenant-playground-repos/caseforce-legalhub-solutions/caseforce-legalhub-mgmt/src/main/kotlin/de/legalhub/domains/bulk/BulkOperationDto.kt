package de.legalhub.domains.bulk

import de.legalhub.model.BulkOperationJob
import io.micronaut.serde.annotation.Serdeable
import java.time.Instant

@Serdeable
data class BulkCaseReassignRequest(
    var targetLawyerId: Long? = null,
    var caseIds: List<Long>? = null,
    var filterPartnerAgencyId: Long? = null,
    var filterLegalField: String? = null,
    var filterStatus: String? = null,
    var filterCurrentLawyerId: Long? = null
)

@Serdeable
data class BulkOperationResponse(
    var id: Long? = null,
    var jobType: String? = null,
    var status: String? = null,
    var requestedById: Long? = null,
    var targetLawyerId: Long? = null,
    var totalCount: Int = 0,
    var processedCount: Int = 0,
    var successCount: Int = 0,
    var failedCount: Int = 0,
    var errorSummary: String? = null,
    var dateCreated: Instant? = null,
    var dateUpdated: Instant? = null
) {
    companion object {
        fun from(entity: BulkOperationJob): BulkOperationResponse {
            return BulkOperationResponse(
                id = entity.id,
                jobType = entity.jobType,
                status = entity.status.name,
                requestedById = entity.requestedBy?.id,
                targetLawyerId = entity.targetLawyer?.id,
                totalCount = entity.totalCount,
                processedCount = entity.processedCount,
                successCount = entity.successCount,
                failedCount = entity.failedCount,
                errorSummary = entity.errorSummary,
                dateCreated = entity.createdAt,
                dateUpdated = entity.updatedAt
            )
        }
    }
}
