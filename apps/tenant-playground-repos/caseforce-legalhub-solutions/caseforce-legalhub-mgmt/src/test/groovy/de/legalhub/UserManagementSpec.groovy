package de.legalhub


import de.legalhub.model.ListResult
import de.legalhub.model.UserRole
import de.legalhub.domains.account.UserCommands
import de.legalhub.domains.account.UserResponse
import io.micronaut.core.type.Argument
import io.micronaut.http.HttpRequest
import io.micronaut.http.HttpStatus
import io.micronaut.http.client.exceptions.HttpClientResponseException

class UserManagementSpec extends BaseSpecification {

    void "can create a new user with roles and credentials"() {
        given:
        def cmd = new UserCommands.Create(
            email: "clerk.anna@legalhero.de",
            firstname: "Anna",
            lastname: "Schmidt",
            password: "SecurePassAnna123!",
            enabled: true,
            roles: [UserRole.Role.CASEFORCE, UserRole.Role.LEGAL_HERO]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.POST("/users", cmd),
            UserResponse
        )

        then:
        response.status() == HttpStatus.CREATED
        def body = response.body()
        body.id != null
        body.email == "clerk.anna@legalhero.de"
        body.firstname == "Anna"
        body.lastname == "Schmidt"
        body.enabled == true
        body.roles.contains("CASEFORCE")
        body.roles.contains("LEGAL_HERO")
    }

    void "cannot create user with duplicate email"() {
        given:
        def cmd = new UserCommands.Create(
            email: "duplicate@legalhero.de",
            firstname: "First",
            lastname: "User",
            password: "Password123"
        )
        apiClient.toBlocking().exchange(HttpRequest.POST("/users", cmd), UserResponse)

        when:
        apiClient.toBlocking().exchange(HttpRequest.POST("/users", cmd), UserResponse)

        then:
        def e = thrown(HttpClientResponseException)
        e.status == HttpStatus.CONFLICT
    }

    void "can get a user by ID"() {
        given:
        def cmd = new UserCommands.Create(
            email: "lawyer.bob@legalhero.de",
            firstname: "Bob",
            lastname: "Miller",
            password: "LawyerPass123!"
        )
        def created = apiClient.toBlocking().exchange(HttpRequest.POST("/users", cmd), UserResponse).body()

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/users/${created.id}"),
            UserResponse
        )

        then:
        response.status() == HttpStatus.OK
        response.body().id == created.id
        response.body().email == "lawyer.bob@legalhero.de"
        response.body().firstname == "Bob"
        response.body().lastname == "Miller"
    }

    void "can list active users"() {
        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.GET("/users"),
            Argument.of(ListResult, UserResponse)
        )

        then:
        response.status() == HttpStatus.OK
        response.body().list.size() >= 1
        response.body().list.any { it.email == EMAIL }
    }

    void "can update user attributes and roles"() {
        given:
        def cmd = new UserCommands.Create(
            email: "clara.update@legalhero.de",
            firstname: "Clara",
            lastname: "Oswald",
            password: "InitPassword123"
        )
        def created = apiClient.toBlocking().exchange(HttpRequest.POST("/users", cmd), UserResponse).body()

        def updateCmd = new UserCommands.Update(
            firstname: "Clara Updated",
            lastname: "Oswald Updated",
            enabled: false,
            roles: [UserRole.Role.ROOT]
        )

        when:
        def response = apiClient.toBlocking().exchange(
            HttpRequest.PUT("/users/${created.id}", updateCmd),
            UserResponse
        )

        then:
        response.status() == HttpStatus.OK
        def body = response.body()
        body.firstname == "Clara Updated"
        body.lastname == "Oswald Updated"
        body.enabled == false
        body.roles.contains("ROOT")
    }

    void "can delete user and soft delete disables account"() {
        given:
        def cmd = new UserCommands.Create(
            email: "to.delete@legalhero.de",
            firstname: "Delete",
            lastname: "Me",
            password: "DeleteMe123"
        )
        def created = apiClient.toBlocking().exchange(HttpRequest.POST("/users", cmd), UserResponse).body()

        when:
        def deleteResponse = apiClient.toBlocking().exchange(
            HttpRequest.DELETE("/users/${created.id}")
        )

        then:
        deleteResponse.status() == HttpStatus.NO_CONTENT

        when:
        apiClient.toBlocking().exchange(HttpRequest.GET("/users/${created.id}"), UserResponse)

        then:
        def e = thrown(HttpClientResponseException)
        e.status == HttpStatus.NOT_FOUND
    }
}
