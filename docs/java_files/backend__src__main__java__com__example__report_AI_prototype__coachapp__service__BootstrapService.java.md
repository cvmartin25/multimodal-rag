# Platzhalter

- **Originalpfad**: `backend/src/main/java/com/example/report_AI_prototype/coachapp/service/BootstrapService.java`
- **Bereich**: Tenancy/Bootstrap (coachProfileId, States, Rollenlogik)

package com.example.report_AI_prototype.coachapp.service;

import org.springframework.stereotype.Service;

import com.example.report_AI_prototype.coachapp.domain.model.CoachClient;
import com.example.report_AI_prototype.coachapp.domain.model.CoachProfile;
import com.example.report_AI_prototype.coachapp.domain.model.UserRole;
import com.example.report_AI_prototype.coachapp.dto.BootstrapResponse;
import com.example.report_AI_prototype.coachapp.repository.CoachClientRepository;
import com.example.report_AI_prototype.coachapp.repository.CoachProfileRepository;
import com.example.report_AI_prototype.model.User;
import com.example.report_AI_prototype.repository.UserRepository;

import java.time.Instant;
import java.util.UUID;

@Service
public class BootstrapService {

    private final UserRepository userRepository;
    private final CoachProfileRepository coachProfileRepository;
    private final CoachClientRepository coachClientRepository;

    public BootstrapService(
        UserRepository userRepository,
        CoachProfileRepository coachProfileRepository,
        CoachClientRepository coachClientRepository
    ) {
        this.userRepository = userRepository;
        this.coachProfileRepository = coachProfileRepository;
        this.coachClientRepository = coachClientRepository;
    }

    public BootstrapResponse getBootstrap(UUID userId) {
        User user = userRepository.findById(userId)
            .orElseThrow(() -> new IllegalArgumentException("User not found"));
        BootstrapResponse response = new BootstrapResponse();
        response.setRole(user.getRole());

        UserRole role = UserRole.fromDb(user.getRole());
        Instant now = Instant.now();

        if (role == UserRole.COACH) {
            CoachProfile profile = coachProfileRepository.findByUserId(userId).orElse(null);
            response.setState("COACH_ACTIVE");
            if (profile != null) {
                response.setCoachProfileId(profile.getId());
                response.setCoachDisplayName(profile.getDisplayName());
            }
            return response;
        }

        CoachClient activeMembership = coachClientRepository.findActiveByClientUserId(userId, now).orElse(null);
        if (activeMembership != null) {
            CoachProfile profile = coachProfileRepository.findById(activeMembership.getCoachProfileId()).orElse(null);
            response.setState("CLIENT_ACTIVE");
            response.setCoachProfileId(activeMembership.getCoachProfileId());
            response.setClientFirstName(activeMembership.getClientFirstName());
            response.setClientLastName(activeMembership.getClientLastName());
            response.setAccessUntil(activeMembership.getAccessUntil());
            if (profile != null) {
                response.setCoachDisplayName(profile.getDisplayName());
            }
            return response;
        }

        response.setState("NEEDS_COACH_CODE");
        return response;
    }
}


