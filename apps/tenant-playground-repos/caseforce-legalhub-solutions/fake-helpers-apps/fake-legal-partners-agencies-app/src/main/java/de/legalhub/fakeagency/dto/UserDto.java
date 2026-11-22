package de.legalhub.fakeagency.dto;

import io.swagger.v3.oas.annotations.media.Schema;

import java.util.List;

@Schema(description = "User details for lawyer or assignee during agency onboarding")
public class UserDto {

    @Schema(description = "User email address", example = "lawyer.weber@berlin-legal.de")
    private String email;

    @Schema(description = "First name", example = "Felix")
    private String firstname;

    @Schema(description = "Last name", example = "Weber")
    private String lastname;

    @Schema(description = "User password (optional, default provided if omitted)", example = "Secret123!")
    private String password;

    @Schema(description = "Whether the user account is active", example = "true")
    private boolean enabled = true;

    @Schema(description = "Roles assigned if user is created", example = "[\"CASEFORCE\", \"LEGAL_HERO\"]")
    private List<String> roles;

    public UserDto() {}

    public UserDto(String email, String firstname, String lastname) {
        this.email = email;
        this.firstname = firstname;
        this.lastname = lastname;
        this.enabled = true;
    }

    public UserDto(String email, String firstname, String lastname, String password, boolean enabled, List<String> roles) {
        this.email = email;
        this.firstname = firstname;
        this.lastname = lastname;
        this.password = password;
        this.enabled = enabled;
        this.roles = roles;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getFirstname() {
        return firstname;
    }

    public void setFirstname(String firstname) {
        this.firstname = firstname;
    }

    public String getLastname() {
        return lastname;
    }

    public void setLastname(String lastname) {
        this.lastname = lastname;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public List<String> getRoles() {
        return roles;
    }

    public void setRoles(List<String> roles) {
        this.roles = roles;
    }
}
