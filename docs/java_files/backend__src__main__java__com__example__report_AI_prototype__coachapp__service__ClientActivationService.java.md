# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/service/ClientActivationService.java`
- **Bereich**: (Optional) Coach Client/Code Flows

package com.example.report_AI_prototype.coachapp.service;

import org.springframework.stereotype.Service;


import org.springframework.transaction.annotation.Transactional;

import com.example.report_AI_prototype.coachapp.domain.model.CoachAccessCode;
import com.example.report_AI_prototype.coachapp.domain.model.CoachClient;
import com.example.report_AI_prototype.coachapp.domain.model.CoachSubscription;
import com.example.report_AI_prototype.coachapp.repository.CoachAccessCodeRepository;
import com.example.report_AI_prototype.coachapp.repository.CoachClientRepository;
import com.example.report_AI_prototype.coachapp.repository.CoachSubscriptionRepository;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.UUID;

@Service
public class ClientActivationService {

    private final CoachAccessCodeRepository coachAccessCodeRepository;
    private final CoachClientRepository coachClientRepository;
    private final CoachSubscriptionRepository coachSubscriptionRepository;
    private final AccessCodeGenerator accessCodeGenerator;

    public ClientActivationService(
        CoachAccessCodeRepository coachAccessCodeRepository,
        CoachClientRepository coachClientRepository,
        CoachSubscriptionRepository coachSubscriptionRepository,
        AccessCodeGenerator accessCodeGenerator
    ) {
        this.coachAccessCodeRepository = coachAccessCodeRepository;
        this.coachClientRepository = coachClientRepository;
        this.coachSubscriptionRepository = coachSubscriptionRepository;
        this.accessCodeGenerator = accessCodeGenerator;
    }

    @Transactional
    public void activate(UUID clientUserId, String rawCode) {
        Instant now = Instant.now();

        String normalized = accessCodeGenerator.normalize(rawCode);
        String hash = HashUtils.sha256Hex(normalized);

        CoachAccessCode code = coachAccessCodeRepository.findByCodeHash(hash)
            .orElseThrow(() -> new IllegalArgumentException("Invalid code"));

        if (!code.isUsableAt(now)) {
            throw new IllegalStateException("Code is not usable");
        }

        CoachSubscription subscription = coachSubscriptionRepository.findByCoachProfileId(code.getCoachProfileId())
            .orElseThrow(() -> new IllegalStateException("Coach subscription not found"));

        if (!"active".equalsIgnoreCase(subscription.getStatus())) {
            throw new IllegalStateException("Coach subscription inactive");
        }

        CoachClient existing;
        if (code.getCoachClientId() != null) {
            existing = coachClientRepository
                .findByIdAndCoachProfileId(code.getCoachClientId(), code.getCoachProfileId())
                .orElseThrow(() -> new IllegalStateException("Code is linked to a missing client"));
            if (existing.getClientUserId() != null && !existing.getClientUserId().equals(clientUserId)) {
                throw new IllegalStateException("Code belongs to another client account");
            }
        } else {
            existing = coachClientRepository
                .findByCoachProfileIdAndClientUserId(code.getCoachProfileId(), clientUserId)
                .orElse(null);
        }

        boolean alreadyActive = existing != null && existing.isActiveNow(now);

        if (!alreadyActive) {
            int activeCount = coachClientRepository.countActiveByCoachProfileId(code.getCoachProfileId(), now);
            if (activeCount >= subscription.getMaxActiveClients()) {
                throw new IllegalStateException("No free active client slots available");
            }
        }

        Instant accessUntil = now.plus(code.getAccessDurationDays(), ChronoUnit.DAYS);

        if (existing == null) {
            coachClientRepository.create(code.getCoachProfileId(), clientUserId, "active", accessUntil);
        } else if (existing.getClientUserId() == null) {
            coachClientRepository.bindUserAndActivate(existing.getId(), clientUserId, accessUntil);
        } else {
            coachClientRepository.reactivate(existing.getId(), accessUntil, "active");
        }

        coachAccessCodeRepository.incrementUsage(code.getId(), now);
    }
}


