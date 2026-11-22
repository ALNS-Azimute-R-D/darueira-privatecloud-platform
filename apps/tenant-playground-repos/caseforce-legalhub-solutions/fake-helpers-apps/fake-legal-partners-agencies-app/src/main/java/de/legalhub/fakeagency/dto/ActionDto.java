package de.legalhub.fakeagency.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.LocalDate;

@Schema(description = "Action or task payload associated with a Legal Case")
public class ActionDto {

    @Schema(description = "Action name or title", example = "Review initial claim documents")
    private String name;

    @Schema(description = "Whether this action is a task", example = "true")
    private boolean isTask;

    @Schema(description = "Status of the action", example = "OPEN")
    private String status = "OPEN";

    @Schema(description = "Assignee user for this action (looked up by email or created)")
    private UserDto assignee;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd")
    @Schema(description = "Due date in YYYY-MM-DD format", example = "2026-12-31")
    private LocalDate dueDate;

    @Schema(description = "Notes or instructions", example = "Verify partner agency authority")
    private String notes;

    public ActionDto() {}

    public ActionDto(String name, boolean isTask, String status, UserDto assignee, LocalDate dueDate, String notes) {
        this.name = name;
        this.isTask = isTask;
        this.status = status;
        this.assignee = assignee;
        this.dueDate = dueDate;
        this.notes = notes;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public boolean isTask() {
        return isTask;
    }

    public void setTask(boolean task) {
        isTask = task;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public UserDto getAssignee() {
        return assignee;
    }

    public void setAssignee(UserDto assignee) {
        this.assignee = assignee;
    }

    public LocalDate getDueDate() {
        return dueDate;
    }

    public void setDueDate(LocalDate dueDate) {
        this.dueDate = dueDate;
    }

    public String getNotes() {
        return notes;
    }

    public void setNotes(String notes) {
        this.notes = notes;
    }
}
