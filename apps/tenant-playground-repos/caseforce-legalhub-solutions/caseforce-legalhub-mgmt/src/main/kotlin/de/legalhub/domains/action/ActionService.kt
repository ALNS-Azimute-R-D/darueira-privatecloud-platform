package de.legalhub.domains.action

import de.legalhub.adapters.output.messaging.RabbitEntityEventClient
import de.legalhub.adapters.output.repository.ActionRepository
import de.legalhub.adapters.output.repository.LegalCaseRepository
import de.legalhub.adapters.output.repository.UserRepository
import de.legalhub.model.Action
import de.legalhub.model.ActionStatus
import de.legalhub.shared.messaging.EntityEvent
import de.legalhub.shared.messaging.EntityType
import jakarta.inject.Singleton
import jakarta.transaction.Transactional

@Singleton
open class ActionService(
    private val actionRepository: ActionRepository,
    private val legalCaseRepository: LegalCaseRepository,
    private val userRepository: UserRepository,
    private val rabbitEntityEventClient: RabbitEntityEventClient,
) {

    fun get(id: Long): Action? {
        return actionRepository.findById(id).orElse(null)
    }

    fun listByLegalCase(legalCaseId: Long): List<Action> {
        return actionRepository.findByLegalCaseId(legalCaseId)
    }

    @Transactional
    open fun create(cmd: ActionCommands.Create, createdByUserId: Long): Action {
        val legalCase = legalCaseRepository.findById(cmd.legalCaseId)
            .orElseThrow { IllegalArgumentException("LegalCase not found: ${cmd.legalCaseId}") }
        val createdBy = userRepository.findById(createdByUserId)
            .orElseThrow { IllegalArgumentException("User not found: $createdByUserId") }

        val action = Action().apply {
            this.legalCase = legalCase
            name = cmd.name
            isTask = cmd.isTask
            assignee = cmd.assigneeId?.let { userRepository.findById(it).orElse(null) }
            this.createdBy = createdBy
            dueDate = cmd.dueDate
            notes = cmd.notes
        }

        val saved = actionRepository.save(action)
        rabbitEntityEventClient.send(EntityEvent(EntityType.ACTION, saved.id!!))
        return saved
    }

    @Transactional
    open fun update(id: Long, cmd: ActionCommands.Update): Action {
        val action = actionRepository.findById(id)
            .orElseThrow { IllegalArgumentException("Action not found: $id") }

        cmd.name?.let { action.name = it }
        cmd.status?.let { action.status = ActionStatus.valueOf(it) }
        cmd.assigneeId?.let { action.assignee = userRepository.findById(it).orElse(null) }
        cmd.dueDate?.let { action.dueDate = it }
        cmd.notes?.let { action.notes = it }

        val updated = actionRepository.update(action)
        rabbitEntityEventClient.send(EntityEvent(EntityType.ACTION, updated.id!!))
        return updated
    }
}
