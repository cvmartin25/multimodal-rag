# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/service/CoachDocumentService.java`
- **Bereich**: Documents (Upload-Contract, Statusmaschine, Storage-Key-Konvention)

package com.example.report_AI_prototype.coachapp.service;

import com.example.report_AI_prototype.coachapp.domain.model.CoachDocument;
import com.example.report_AI_prototype.coachapp.domain.model.CoachProfile;
import com.example.report_AI_prototype.coachapp.dto.BeginCoachDocumentUploadRequest;
import com.example.report_AI_prototype.coachapp.dto.BeginCoachDocumentUploadResponse;
import com.example.report_AI_prototype.coachapp.dto.CoachDocumentSummary;
import com.example.report_AI_prototype.coachapp.dto.CompleteCoachDocumentUploadRequest;
import com.example.report_AI_prototype.coachapp.repository.CoachDocumentRepository;
import com.example.report_AI_prototype.coachapp.repository.CoachProfileRepository;
import com.example.report_AI_prototype.service.StorageService;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.net.URI;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
public class CoachDocumentService {

    private final CoachProfileRepository coachProfileRepository;
    private final CoachDocumentRepository coachDocumentRepository;
    private final StorageService storageService;

    @Value("${storage.s3.documents-bucket}")
    private String documentsBucket;

    public CoachDocumentService(
        CoachProfileRepository coachProfileRepository,
        CoachDocumentRepository coachDocumentRepository,
        StorageService storageService
    ) {
        this.coachProfileRepository = coachProfileRepository;
        this.coachDocumentRepository = coachDocumentRepository;
        this.storageService = storageService;
    }

    @Transactional
    public BeginCoachDocumentUploadResponse beginUpload(UUID coachUserId, BeginCoachDocumentUploadRequest request) {
        CoachProfile profile = resolveCoachProfile(coachUserId);

        String originalFilename = request.getOriginalFilename().trim();
        if (originalFilename.isBlank()) {
            throw new IllegalArgumentException("originalFilename must not be blank");
        }

        UUID documentId = UUID.randomUUID();
        String storageKey = buildStorageKey(profile.getId(), documentId);

        CoachDocument created = coachDocumentRepository.createPendingUpload(
            documentId,
            profile.getId(),
            originalFilename,
            documentsBucket,
            storageKey,
            normalizeBlankToNull(request.getMimeType()),
            request.getExpectedSizeBytes(),
            coachUserId
        );

        URI uploadUrl = storageService.createPresignedUploadUrl(documentsBucket, storageKey, 300);

        BeginCoachDocumentUploadResponse response = new BeginCoachDocumentUploadResponse();
        response.setDocumentId(created.getId());
        response.setUploadUrl(uploadUrl);
        return response;
    }

    @Transactional
    public CoachDocumentSummary completeUpload(UUID coachUserId, UUID documentId, CompleteCoachDocumentUploadRequest request) {
        CoachProfile profile = resolveCoachProfile(coachUserId);

        CoachDocument existing = coachDocumentRepository.findByIdAndCoachProfileId(documentId, profile.getId())
            .orElseThrow(() -> new IllegalArgumentException("Document not found"));

        if (!"pending_upload".equalsIgnoreCase(existing.getStatus())) {
            throw new IllegalStateException("Only pending uploads can be completed");
        }

        long sizeBytes = request.getSizeBytes();
        if (sizeBytes <= 0) {
            throw new IllegalArgumentException("sizeBytes must be > 0");
        }

        CoachDocument updated = coachDocumentRepository.markUploaded(
            existing.getId(),
            profile.getId(),
            normalizeBlankToNull(request.getMimeType()),
            sizeBytes,
            Instant.now()
        );

        return toSummary(updated);
    }

    public List<CoachDocumentSummary> list(UUID coachUserId) {
        CoachProfile profile = resolveCoachProfile(coachUserId);
        return coachDocumentRepository.findByCoachProfileId(profile.getId()).stream()
            .map(this::toSummary)
            .toList();
    }

    @Transactional
    public void delete(UUID coachUserId, UUID documentId) {
        CoachProfile profile = resolveCoachProfile(coachUserId);

        CoachDocument existing = coachDocumentRepository.findByIdAndCoachProfileId(documentId, profile.getId())
            .orElseThrow(() -> new IllegalArgumentException("Document not found"));

        String status = existing.getStatus() != null ? existing.getStatus().trim().toLowerCase() : "";
        if ("processing".equals(status) || "active".equals(status)) {
            throw new IllegalStateException("Documents in processing/active state cannot be deleted");
        }

        int deleted = coachDocumentRepository.deleteByIdAndCoachProfileId(documentId, profile.getId());
        if (deleted == 0) {
            throw new IllegalArgumentException("Document not found");
        }
    }

    private CoachProfile resolveCoachProfile(UUID coachUserId) {
        return coachProfileRepository.findByUserId(coachUserId)
            .orElseThrow(() -> new IllegalStateException("Coach profile not found"));
    }

    private String buildStorageKey(UUID coachProfileId, UUID documentId) {
        return "mycoach/" + coachProfileId + "/documents/" + documentId + "/original";
    }

    private String normalizeBlankToNull(String s) {
        if (s == null) return null;
        String t = s.trim();
        return t.isBlank() ? null : t;
    }

    private CoachDocumentSummary toSummary(CoachDocument doc) {
        CoachDocumentSummary s = new CoachDocumentSummary();
        s.setId(doc.getId());
        s.setOriginalFilename(doc.getOriginalFilename());
        s.setMimeType(doc.getMimeType());
        s.setFileSizeBytes(doc.getFileSizeBytes());
        s.setStatus(doc.getStatus());
        s.setCreatedAt(doc.getCreatedAt());
        s.setUploadedAt(doc.getUploadedAt());
        s.setProcessingStartedAt(doc.getProcessingStartedAt());
        s.setProcessedAt(doc.getProcessedAt());
        s.setErrorMessage(doc.getErrorMessage());
        return s;
    }
}




