# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/controller/CoachDocumentController.java`
- **Bereich**: Documents (Upload-Contract, Statusmaschine, Storage-Key-Konvention)

package com.example.report_AI_prototype.coachapp.controller;

import com.example.report_AI_prototype.coachapp.dto.BeginCoachDocumentUploadRequest;
import com.example.report_AI_prototype.coachapp.dto.BeginCoachDocumentUploadResponse;
import com.example.report_AI_prototype.coachapp.dto.CoachDocumentSummary;
import com.example.report_AI_prototype.coachapp.dto.CompleteCoachDocumentUploadRequest;
import com.example.report_AI_prototype.coachapp.service.CoachDocumentService;
import com.example.report_AI_prototype.security.SecurityUtils;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/coach")
public class CoachDocumentController {

    private final CoachDocumentService coachDocumentService;

    public CoachDocumentController(CoachDocumentService coachDocumentService) {
        this.coachDocumentService = coachDocumentService;
    }

    private UUID currentUserIdOrThrow() {
        return SecurityUtils.currentUserId()
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Unauthorized"));
    }

    @GetMapping("/documents")
    public ResponseEntity<List<CoachDocumentSummary>> list() {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachDocumentService.list(userId));
    }

    @PostMapping("/documents:begin-upload")
    public ResponseEntity<BeginCoachDocumentUploadResponse> beginUpload(
        @Valid @RequestBody BeginCoachDocumentUploadRequest request
    ) {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachDocumentService.beginUpload(userId, request));
    }

    @PostMapping("/documents/{documentId}:complete-upload")
    public ResponseEntity<CoachDocumentSummary> completeUpload(
        @PathVariable UUID documentId,
        @Valid @RequestBody CompleteCoachDocumentUploadRequest request
    ) {
        UUID userId = currentUserIdOrThrow();
        return ResponseEntity.ok(coachDocumentService.completeUpload(userId, documentId, request));
    }

    @DeleteMapping("/documents/{documentId}")
    public ResponseEntity<Void> delete(@PathVariable UUID documentId) {
        UUID userId = currentUserIdOrThrow();
        coachDocumentService.delete(userId, documentId);
        return ResponseEntity.noContent().build();
    }
}




