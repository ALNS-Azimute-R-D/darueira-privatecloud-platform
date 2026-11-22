package de.legalhub

import de.legalhub.domains.account.GroupCommands
import de.legalhub.domains.account.GroupResponse
import de.legalhub.domains.account.UserGroupMembershipResponse
import de.legalhub.model.ListResult
import de.legalhub.domains.account.UserCommands
import de.legalhub.domains.account.UserResponse
import io.micronaut.core.type.Argument
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpStatus
import io.micronaut.http.client.exceptions.HttpClientResponseException

class GroupManagementSpec extends BaseSpecification {

    void "can create a new permission group"() {
        given:
        def cmd = new GroupCommands.Create(
            name: "JuniorLawyers",
            permissions: ["CASE_GET", "CASE_LIST", "ACTION_GET", "ACTION_LIST"]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/groups", cmd),
            GroupResponse
        )

        then:
        response.status() == HttpStatus.CREATED
        def body = response.body()
        body.id != null
        body.name == "JuniorLawyers"
        body.permissions.size() == 4
        body.permissions.contains("CASE_GET")
    }

    void "cannot create group with duplicate name"() {
        given:
        def cmd = new GroupCommands.Create(
            name: "DuplicateGroup",
            permissions: ["CASE_GET"]
        )
        apiClient.toBlocking().exchange(HttpRequest.POST("/groups", cmd), GroupResponse)

        when:
        apiClient.toBlocking().exchange(HttpRequest.POST("/groups", cmd), GroupResponse)

        then:
        def e = thrown(HttpClientResponseException)
        e.status == HttpStatus.CONFLICT
    }

    void "can get group by ID"() {
        given:
        def cmd = new GroupCommands.Create(
            name: "CaseInvestigators",
            permissions: ["CASE_GET", "CASE_UPDATE"]
        )
        def created = apiClient.toBlocking().exchange(HttpRequest.POST("/groups", cmd), GroupResponse).body()

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/groups/${created.id}"),
            GroupResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().id == created.id
        response.body().name == "CaseInvestigators"
    }

    void "can update group name and permissions"() {
        given:
        def cmd = new GroupCommands.Create(
            name: "Paralegals",
            permissions: ["CASE_GET"]
        )
        def created = apiClient.toBlocking().exchange(HttpRequest.POST("/groups", cmd), GroupResponse).body()

        def updateCmd = new GroupCommands.Update(
            name: "SeniorParalegals",
            permissions: ["CASE_GET", "CASE_CREATE", "CASE_UPDATE"]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.PUT("/groups/${created.id}", updateCmd),
            GroupResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().name == "SeniorParalegals"
        response.body().permissions.size() == 3
    }

    void "can delete group"() {
        given:
        def cmd = new GroupCommands.Create(
            name: "TemporaryGroup",
            permissions: ["ACTION_GET"]
        )
        def created = apiClient.toBlocking().exchange(HttpRequest.POST("/groups", cmd), GroupResponse).body()

        when:
        def deleteResponse = apiClient.toBlocking().exchange(
            HttpRequest.DELETE("/groups/${created.id}")
        )

        then:
        deleteResponse.status() == HttpStatus.NO_CONTENT

        when:
        apiClient.toBlocking().exchange(HttpRequest.GET("/groups/${created.id}"), GroupResponse)

        then:
        def e = thrown(HttpClientResponseException)
        e.status == HttpStatus.NOT_FOUND
    }

    void "can manage group memberships: add, list, and remove member"() {
        given:
        def userCmd = new UserCommands.Create(
            email: "member.test@legalhero.de",
            firstname: "Member",
            lastname: "User",
            password: "MemberPass123!"
        )
        def memberUser = apiClient.toBlocking().exchange(HttpRequest.POST("/users", userCmd), UserResponse).body()

        def groupCmd = new GroupCommands.Create(
            name: "LegalReviewers",
            permissions: ["CASE_GET", "CASE_LIST", "CASE_UPDATE"]
        )
        def reviewerGroup = apiClient.toBlocking().exchange(HttpRequest.POST("/groups", groupCmd), GroupResponse).body()

        when: "Adding user to group via path"
        def addResponse = apiClient.toBlocking().exchange(
            HttpRequest.POST("/groups/${reviewerGroup.id}/members/${memberUser.id}", [:]),
            UserGroupMembershipResponse
        )

        then:
        addResponse.status() == HttpStatus.OK
        addResponse.body().userId == memberUser.id
        addResponse.body().groupId == reviewerGroup.id

        when: "Listing members of the group"
        def listMembersResp = apiClient.toBlocking().exchange(
            HttpRequest.GET("/groups/${reviewerGroup.id}/members"),
            Argument.of(ListResult, UserResponse)
        )

        then:
        listMembersResp.status() == HttpStatus.OK
        listMembersResp.body().list.any { it.id == memberUser.id }

        when: "Listing groups for the user"
        def listUserGroupsResp = apiClient.toBlocking().exchange(
            HttpRequest.GET("/users/${memberUser.id}/groups"),
            Argument.of(ListResult, GroupResponse)
        )

        then:
        listUserGroupsResp.status() == HttpStatus.OK
        listUserGroupsResp.body().list.any { it.id == reviewerGroup.id }

        when: "Removing member from group"
        def removeResp = apiClient.toBlocking().exchange(
            HttpRequest.DELETE("/groups/${reviewerGroup.id}/members/${memberUser.id}")
        )

        then:
        removeResp.status() == HttpStatus.NO_CONTENT

        when: "Listing members again"
        def listMembersAfterResp = apiClient.toBlocking().exchange(
            HttpRequest.GET("/groups/${reviewerGroup.id}/members"),
            Argument.of(ListResult, UserResponse)
        )

        then:
        !listMembersAfterResp.body().list.any { it.id == memberUser.id }
    }
}
