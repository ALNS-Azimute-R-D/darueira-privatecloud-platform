package de.legalhub.domains.bulk

import de.legalhub.adapters.output.messaging.RabbitEntityEventClient
import de.legalhub.adapters.output.repository.BulkOperationJobRepository
import de.legalhub.adapters.output.repository.LegalCaseRepository
import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.model.BulkOperationJob
import de.legalhub.model.LegalCase
import de.legalhub.model.User
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import io.micronaut.http.HttpStatus
import io.micronaut.http.exceptions.HttpStatusException
import io.micronaut.serde.ObjectMapper
import jakarta.inject.Singleton
import jakarta.transaction.Transactional
import org.slf4j.LoggerFactory

@Singleton
open class BulkOperationService(
    private val bulkOperationJobRepository: BulkOperationJobRepository,
    private val legalCaseRepository: LegalCaseRepository,
    private val userRepository: UserRepository,
    private val rabbitEntityEventClient: RabbitEntityEventClient,
    private val objectMapper: ObjectMapper
) {

    private val log = LoggerFactory.getLogger(BulkOperationService::class.java)

    fun get(id: Long): BulkOperationJob? {
        return bulkOperationJobRepository.findById(id).orElse(null)
    }

    @Transactional
    open fun submitReassignJob(req: BulkCaseReassignRequest, requestingUser: User?): BulkOperationJob {
        val targetLawyerId = req.targetLawyerId
            ?: throw HttpStatusException(HttpStatus.BAD_REQUEST, "targetLawyerId is required")

        val targetLawyer = userRepository.findById(targetLawyerId)
            .orElseThrow { HttpStatusException(HttpStatus.NOT_FOUND, "Target lawyer not found: $targetLawyerId") }

        val candidateCases = findCandidateCases(req)

        val job = BulkOperationJob().apply {
            this.jobType = "CASE_REASSIGNMENT"
            this.status = BulkOperationJob.Status.PENDING
            this.requestedBy = requestingUser
            this.targetLawyer = targetLawyer
            this.filterCriteria = objectMapper.writeValueAsString(req)
            this.totalCount = candidateCases.size
            this.processedCount = 0
            this.successCount = 0
            this.failedCount = 0
        }

        val savedJob = bulkOperationJobRepository.save(job)
        executeReassignJob(savedJob.id!!, candidateCases.mapNotNull { it.id }, targetLawyerId)
        return savedJob
    }

    open fun executeReassignJob(jobId: Long, caseIds: List<Long>, targetLawyerId: Long) {
        val job = bulkOperationJobRepository.findById(jobId).orElse(null) ?: return
        val targetLawyer = userRepository.findById(targetLawyerId).orElse(null) ?: return

        job.status = BulkOperationJob.Status.IN_PROGRESS
        bulkOperationJobRepository.update(job)

        val errors = mutableListOf<String>()

        for (caseId in caseIds) {
            try {
                reassignSingleCase(caseId, targetLawyer)
                job.successCount += 1
            } catch (e: Exception) {
                job.failedCount += 1
                errors.add("Case $caseId: ${e.message}")
                log.error("Failed to reassign case $caseId", e)
            } finally {
                job.processedCount += 1
            }
        }

        job.status = if (job.failedCount == 0) {
            BulkOperationJob.Status.COMPLETED
        } else if (job.successCount > 0) {
            BulkOperationJob.Status.COMPLETED
        } else {
            BulkOperationJob.Status.FAILED
        }

        if (errors.isNotEmpty()) {
            job.errorSummary = objectMapper.writeValueAsString(errors)
        }

        bulkOperationJobRepository.update(job)
    }

    @Transactional
    open fun reassignSingleCase(caseId: Long, targetLawyer: User) {
        val case = legalCaseRepository.findById(caseId).orElseThrow {
            IllegalArgumentException("Case $caseId not found")
        }
        case.lawyer = targetLawyer
        legalCaseRepository.update(case)
        rabbitEntityEventClient.send(EntityEvent(EntityType.LEGAL_CASE, caseId))
    }

    private fun findCandidateCases(req: BulkCaseReassignRequest): List<LegalCase> {
        val allCases = legalCaseRepository.findByDeletedAtIsNull()
        return allCases.filter { c ->
            val matchesIds = req.caseIds == null || req.caseIds!!.contains(c.id)
            val matchesAgency = req.filterPartnerAgencyId == null || c.partnerAgency?.id == req.filterPartnerAgencyId
            val matchesField = req.filterLegalField == null || c.legalField == req.filterLegalField
            val matchesStatus = req.filterStatus == null || c.status.name == req.filterStatus
            val matchesCurrentLawyer = req.filterCurrentLawyerId == null || c.lawyer?.id == req.filterCurrentLawyerId

            matchesIds && matchesAgency && matchesField && matchesStatus && matchesCurrentLawyer
        }
    }
}
