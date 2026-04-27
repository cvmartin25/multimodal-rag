# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/repository/CoachDocumentRepository.java`
- **Bereich**: Documents (Upload-Contract, Statusmaschine, Storage-Key-Konvention)

package com.example.report_AI_prototype.coachapp.repository;

import com.example.report_AI_prototype.coachapp.domain.model.CoachDocument;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public class CoachDocumentRepository {

    private final NamedParameterJdbcTemplate jdbc;

    public CoachDocumentRepository(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    private final RowMapper<CoachDocument> rowMapper = (rs, rowNum) -> {
        CoachDocument d = new CoachDocument();
        d.setId(rs.getObject("id", UUID.class));
        d.setCoachProfileId(rs.getObject("coach_profile_id", UUID.class));
        d.setOriginalFilename(rs.getString("original_filename"));
        d.setStorageBucket(rs.getString("storage_bucket"));
        d.setStorageKey(rs.getString("storage_key"));
        d.setMimeType(rs.getString("mime_type"));
        Long size = rs.getObject("file_size_bytes", Long.class);
        d.setFileSizeBytes(size);
        d.setStatus(rs.getString("status"));
        d.setUploadedByUserId(rs.getObject("uploaded_by_user_id", UUID.class));

        Timestamp createdAt = rs.getTimestamp("created_at");
        Timestamp uploadedAt = rs.getTimestamp("uploaded_at");
        Timestamp processingStartedAt = rs.getTimestamp("processing_started_at");
        Timestamp processedAt = rs.getTimestamp("processed_at");
        d.setCreatedAt(createdAt != null ? createdAt.toInstant() : null);
        d.setUploadedAt(uploadedAt != null ? uploadedAt.toInstant() : null);
        d.setProcessingStartedAt(processingStartedAt != null ? processingStartedAt.toInstant() : null);
        d.setProcessedAt(processedAt != null ? processedAt.toInstant() : null);
        d.setErrorMessage(rs.getString("error_message"));
        return d;
    };

    public CoachDocument createPendingUpload(
        UUID id,
        UUID coachProfileId,
        String originalFilename,
        String storageBucket,
        String storageKey,
        String mimeType,
        Long expectedSizeBytes,
        UUID uploadedByUserId
    ) {
        String sql = """
            insert into coach_documents (
                id,
                coach_profile_id,
                original_filename,
                storage_bucket,
                storage_key,
                mime_type,
                file_size_bytes,
                status,
                uploaded_by_user_id
            )
            values (
                :id,
                :coachProfileId,
                :originalFilename,
                :storageBucket,
                :storageKey,
                :mimeType,
                :fileSizeBytes,
                'pending_upload',
                :uploadedByUserId
            )
            returning
                id, coach_profile_id, original_filename, storage_bucket, storage_key, mime_type, file_size_bytes,
                status, uploaded_by_user_id, created_at, uploaded_at, processing_started_at, processed_at, error_message
            """;

        return jdbc.queryForObject(sql,
            new MapSqlParameterSource()
                .addValue("id", id)
                .addValue("coachProfileId", coachProfileId)
                .addValue("originalFilename", originalFilename)
                .addValue("storageBucket", storageBucket)
                .addValue("storageKey", storageKey)
                .addValue("mimeType", mimeType)
                .addValue("fileSizeBytes", expectedSizeBytes)
                .addValue("uploadedByUserId", uploadedByUserId),
            rowMapper);
    }

    public Optional<CoachDocument> findByIdAndCoachProfileId(UUID id, UUID coachProfileId) {
        String sql = """
            select
                id, coach_profile_id, original_filename, storage_bucket, storage_key, mime_type, file_size_bytes,
                status, uploaded_by_user_id, created_at, uploaded_at, processing_started_at, processed_at, error_message
            from coach_documents
            where id = :id
              and coach_profile_id = :coachProfileId
            """;
        return jdbc.query(sql,
            new MapSqlParameterSource()
                .addValue("id", id)
                .addValue("coachProfileId", coachProfileId),
            rowMapper).stream().findFirst();
    }

    public List<CoachDocument> findByCoachProfileId(UUID coachProfileId) {
        String sql = """
            select
                id, coach_profile_id, original_filename, storage_bucket, storage_key, mime_type, file_size_bytes,
                status, uploaded_by_user_id, created_at, uploaded_at, processing_started_at, processed_at, error_message
            from coach_documents
            where coach_profile_id = :coachProfileId
            order by created_at desc
            """;
        return jdbc.query(sql,
            new MapSqlParameterSource().addValue("coachProfileId", coachProfileId),
            rowMapper);
    }

    public CoachDocument markUploaded(UUID id, UUID coachProfileId, String mimeType, long sizeBytes, Instant uploadedAt) {
        String sql = """
            update coach_documents
            set status = 'uploaded',
                mime_type = COALESCE(:mimeType, mime_type),
                file_size_bytes = :fileSizeBytes,
                uploaded_at = :uploadedAt
            where id = :id
              and coach_profile_id = :coachProfileId
            returning
                id, coach_profile_id, original_filename, storage_bucket, storage_key, mime_type, file_size_bytes,
                status, uploaded_by_user_id, created_at, uploaded_at, processing_started_at, processed_at, error_message
            """;

        return jdbc.queryForObject(sql,
            new MapSqlParameterSource()
                .addValue("id", id)
                .addValue("coachProfileId", coachProfileId)
                .addValue("mimeType", mimeType)
                .addValue("fileSizeBytes", sizeBytes)
                .addValue("uploadedAt", Timestamp.from(uploadedAt)),
            rowMapper);
    }

    public int deleteByIdAndCoachProfileId(UUID id, UUID coachProfileId) {
        String sql = """
            delete from coach_documents
            where id = :id
              and coach_profile_id = :coachProfileId
            """;
        return jdbc.update(sql,
            new MapSqlParameterSource()
                .addValue("id", id)
                .addValue("coachProfileId", coachProfileId));
    }
}




