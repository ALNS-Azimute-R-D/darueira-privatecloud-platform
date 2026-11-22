package de.legalhub.domains.legalcase

import io.micronaut.serde.annotation.Serdeable

object LegalCaseCommands {

    @Serdeable
    data class Create(
        var caseNumber: String? = null,
        var legalField: String? = null,
        var summary: String? = null,
        var lawyerId: Long? = null,
        var assigneeId: Long? = null,
        var partnerAgencyAlias: String? = null,
    )

    @Serdeable
    data class Update(
        var caseNumber: String? = null,
        var legalField: String? = null,
        var status: String? = null,
        var summary: String? = null,
        var lawyerId: Long? = null,
        var assigneeId: Long? = null,
    )
}
