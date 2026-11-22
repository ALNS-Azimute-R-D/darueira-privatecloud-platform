package de.legalhub.domains.legalcase

import de.legalhub.adapters.output.messaging.RabbitEntityEventClient
import de.legalhub.adapters.output.repository.LegalCaseRepository
import de.legalhub.adapters.output.repository.PartnerAgencyRepository
import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.model.CaseStatus
import de.legalhub.model.LegalCase
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import jakarta.inject.Singleton
import jakarta.transaction.Transactional

@Singleton
open class LegalCaseService(
    private val legalCaseRepository: LegalCaseRepository,
    private val userRepository: UserRepository,
    private val partnerAgencyRepository: PartnerAgencyRepository,
    private val rabbitEntityEventClient: RabbitEntityEventClient,
) {

    fun get(id: Long): LegalCase? {
        return legalCaseRepository.findById(id).orElse(null)
    }

    fun list(): List<LegalCase> {
        return legalCaseRepository.findByDeletedAtIsNull()
    }

    @Transactional
    open fun create(cmd: LegalCaseCommands.Create): LegalCase {
        val legalCase = LegalCase().apply {
            caseNumber = cmd.caseNumber
            legalField = cmd.legalField
            summary = cmd.summary
            lawyer = cmd.lawyerId?.let { userRepository.findById(it).orElse(null) }
            assignee = cmd.assigneeId?.let { userRepository.findById(it).orElse(null) }
            partnerAgency = cmd.partnerAgencyAlias?.let { partnerAgencyRepository.findByAlias(it).orElse(null) }
        }
        val saved = legalCaseRepository.save(legalCase)
        rabbitEntityEventClient.send(EntityEvent(EntityType.LEGAL_CASE, saved.id!!))
        return saved
    }

    @Transactional
    open fun update(id: Long, cmd: LegalCaseCommands.Update): LegalCase {
        val legalCase = legalCaseRepository.findById(id)
            .orElseThrow { IllegalArgumentException("LegalCase not found: $id") }

        cmd.caseNumber?.let { legalCase.caseNumber = it }
        cmd.legalField?.let { legalCase.legalField = it }
        cmd.status?.let { legalCase.status = CaseStatus.valueOf(it) }
        cmd.summary?.let { legalCase.summary = it }
        cmd.lawyerId?.let { legalCase.lawyer = userRepository.findById(it).orElse(null) }
        cmd.assigneeId?.let { legalCase.assignee = userRepository.findById(it).orElse(null) }

        val updated = legalCaseRepository.update(legalCase)
        rabbitEntityEventClient.send(EntityEvent(EntityType.LEGAL_CASE, updated.id!!))
        return updated
    }
}
