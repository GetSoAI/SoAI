/* SoAI - Active chat stream follower synchronization [frontend/assets/ts/features/chat/chatstreamservice/activeStatusFollowerSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { identitiesMatchActiveStatus, type ActiveChatStreamStatus, type ChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import { applyAssistantMessageSnapshot, applyStatusPreviewSnapshot, createActiveFollowerSession, fetchFollowerMessageSnapshot, sessionMatchesActiveStatus } from '@features/chat/chatstreamservice/activeStatusSessionState.ts';
import { fetchCurrentChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStatusAdmissionCommit.ts';
import { finalizeInactiveFollowerFromHydratedMessage, finalizeInactiveOwnerSession, terminalizeInactiveFollower, waitForInactiveTerminalSnapshot, type ActiveStatusInactiveTransitionArguments, type InactiveTerminalizationResult } from '@features/chat/chatstreamservice/activeStatusInactiveTransition.ts';
import { deactivateFollowerSession } from '@features/chat/chatstreamservice/activeStatusFollowerDisposal.ts';
import { activeStatusPrecedesSession, discardOwnerSession, handleIgnoredActiveStatus, releaseStaleOwnerSession } from '@features/chat/chatstreamservice/activeStatusSessionCleanup.ts';
import { requireCanonicalMessageLoad, skipCanonicalMessageLoad, type ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import { resolveHydratedTerminalStatusFromMessage } from '@features/chat/chatstreamservice/streamHydratedTerminalStatus.ts';
import type { ChatStreamSession, ChatStreamStartAdmission } from '@features/chat/chatstreamservice/types.ts';

type ActiveStatusFollowerSyncArguments = ActiveStatusInactiveTransitionArguments & {
    conversationId: string;
};

const MAX_STATUS_SYNC_ATTEMPTS = 3;
const MAX_TERMINAL_RECONCILIATION_ATTEMPTS = 3;
const MAX_INACTIVE_STATUS_RECONCILIATION_ATTEMPTS = 3;

const resolveInactiveTerminalizationReconciliation = (result: InactiveTerminalizationResult, startAdmission: ChatStreamStartAdmission = 'inactive'): ChatStreamMessageSavedReconciliation | null => {
    if (result === 'hydrated-terminal') {
        return requireCanonicalMessageLoad('terminalized-session', startAdmission);
    }
    if (result === 'missing-terminal-snapshot') {
        return requireCanonicalMessageLoad('inactive-no-stream-session', startAdmission);
    }
    if (result === 'suppressed') {
        return requireCanonicalMessageLoad('suppressed-or-superseded-active-status');
    }
    return null;
};

const reconcileCurrentSessionForTerminalSnapshot = async (inputArguments: ActiveStatusFollowerSyncArguments, status: ActiveChatStreamStatus, assistantMessage: ChatStreamSession['assistantMessage']): Promise<ChatStreamMessageSavedReconciliation | null> => {
    for (let attempt = 0; attempt < MAX_TERMINAL_RECONCILIATION_ATTEMPTS; attempt += 1) {
        const currentSession = inputArguments.sessions.get(status.conversationId);
        if (!currentSession) {
            return null;
        }
        if (!currentSession.active) {
            discardOwnerSession(inputArguments, status.conversationId, currentSession);
            return null;
        }
        if (activeStatusPrecedesSession(status, currentSession)) {
            return skipCanonicalMessageLoad('active-stream', 'busy');
        }
        if (currentSession.transportMode === 'owner') {
            if (sessionMatchesActiveStatus(currentSession, status)) {
                return resolveInactiveTerminalizationReconciliation(await finalizeInactiveOwnerSession(inputArguments, status, currentSession, assistantMessage), 'busy');
            }
            releaseStaleOwnerSession(inputArguments, status.conversationId, currentSession);
            continue;
        }
        if (sessionMatchesActiveStatus(currentSession, status)) {
            return resolveInactiveTerminalizationReconciliation(await finalizeInactiveFollowerFromHydratedMessage(inputArguments, currentSession, assistantMessage));
        }
        deactivateFollowerSession(inputArguments, status.conversationId, currentSession);
    }
    throw new Error('Chat stream terminal reconciliation changed repeatedly.');
};

const reconcileCurrentInactiveSession = async (inputArguments: ActiveStatusFollowerSyncArguments, conversationId: string, startAdmission: ChatStreamStartAdmission = 'inactive'): Promise<ChatStreamMessageSavedReconciliation> => {
    for (let attempt = 0; attempt < MAX_INACTIVE_STATUS_RECONCILIATION_ATTEMPTS; attempt += 1) {
        const currentSession = inputArguments.sessions.get(conversationId);
        if (!currentSession || !currentSession.active) {
            return requireCanonicalMessageLoad('inactive-no-stream-session', startAdmission);
        }
        if (currentSession.transportMode === 'follower') {
            const reconciliation = resolveInactiveTerminalizationReconciliation(await terminalizeInactiveFollower(inputArguments, conversationId, currentSession.requestId), startAdmission);
            if (reconciliation !== null) {
                return reconciliation;
            }
            continue;
        }
        const reconciliation = resolveInactiveTerminalizationReconciliation(
            await finalizeInactiveOwnerSession(
                inputArguments,
                {
                    conversationId: currentSession.conversationId,
                    requestId: currentSession.requestId,
                    assistantTimestamp: currentSession.assistantTimestamp,
                    assistantTurnTimestamp: currentSession.assistantTurnTimestamp,
                    modelVariantIndex: currentSession.modelVariantIndex
                },
                currentSession,
                currentSession.assistantMessage
            ),
            startAdmission
        );
        if (reconciliation !== null) {
            return reconciliation;
        }
    }
    throw new Error('Chat stream inactive-status reconciliation changed repeatedly.');
};

const reconcileInactiveStatusSnapshot = async (inputArguments: ActiveStatusFollowerSyncArguments, status: ChatStreamStatusSnapshot): Promise<ChatStreamMessageSavedReconciliation> => {
    if (status.active) {
        return skipCanonicalMessageLoad('active-stream', 'busy');
    }
    if (status.startAdmission === 'unknown') {
        return requireCanonicalMessageLoad('status-sync-timeout', 'unknown');
    }
    const currentSession = inputArguments.sessions.get(status.conversationId);
    if (status.startAdmission === 'busy' && status.requestId !== null && currentSession?.active === true && currentSession.status === 'streaming' && currentSession.requestId === status.requestId) {
        return skipCanonicalMessageLoad('active-stream', 'busy');
    }
    return await reconcileCurrentInactiveSession(inputArguments, status.conversationId, status.startAdmission);
};

const syncActiveFollower = async (inputArguments: ActiveStatusFollowerSyncArguments, status: ActiveChatStreamStatus): Promise<ChatStreamMessageSavedReconciliation> => {
    let candidateStatus = status;
    for (let attempt = 0; attempt < MAX_STATUS_SYNC_ATTEMPTS; attempt += 1) {
        if (!inputArguments.isCurrent()) {
            return requireCanonicalMessageLoad('stale-generation');
        }
        if (inputArguments.requestDispositions.shouldIgnorePassiveStreamEvent(candidateStatus.conversationId, candidateStatus.requestId)) {
            handleIgnoredActiveStatus(inputArguments, candidateStatus);
            return requireCanonicalMessageLoad('suppressed-or-superseded-active-status');
        }
        const assistantMessage = await fetchFollowerMessageSnapshot(inputArguments.apiClient, candidateStatus, inputArguments.isCurrent, inputArguments.signal);
        if (!inputArguments.isCurrent()) {
            return requireCanonicalMessageLoad('stale-generation');
        }
        if (assistantMessage === null) {
            const latestStatus = await fetchCurrentChatStreamStatusSnapshot(inputArguments);
            if (latestStatus === null) {
                return requireCanonicalMessageLoad('stale-generation');
            }
            if (latestStatus.active && !identitiesMatchActiveStatus(latestStatus, candidateStatus)) {
                candidateStatus = latestStatus;
                continue;
            }
            if (!latestStatus.active) {
                return await reconcileInactiveStatusSnapshot(inputArguments, latestStatus);
            }
            return requireCanonicalMessageLoad();
        }
        const hydratedTerminalStatus = resolveHydratedTerminalStatusFromMessage(assistantMessage);
        if (hydratedTerminalStatus !== null) {
            const reconciliation = await reconcileCurrentSessionForTerminalSnapshot(inputArguments, candidateStatus, assistantMessage);
            if (reconciliation !== null) {
                return reconciliation;
            }
            const terminalSession = createActiveFollowerSession(candidateStatus, assistantMessage);
            inputArguments.sessions.set(candidateStatus.conversationId, terminalSession);
            await finalizeInactiveFollowerFromHydratedMessage(inputArguments, terminalSession, assistantMessage);
            return requireCanonicalMessageLoad('terminalized-session', 'busy');
        }
        const latestStatus = await fetchCurrentChatStreamStatusSnapshot(inputArguments);
        if (latestStatus === null) {
            return requireCanonicalMessageLoad('stale-generation');
        }
        if (latestStatus.active && inputArguments.requestDispositions.shouldIgnorePassiveStreamEvent(latestStatus.conversationId, latestStatus.requestId)) {
            handleIgnoredActiveStatus(inputArguments, latestStatus);
            return requireCanonicalMessageLoad('suppressed-or-superseded-active-status');
        }
        if (!latestStatus.active) {
            return await syncInactiveFollowerSnapshot(inputArguments, candidateStatus, latestStatus, assistantMessage);
        }
        if (!identitiesMatchActiveStatus(latestStatus, candidateStatus)) {
            candidateStatus = latestStatus;
            continue;
        }
        const current = inputArguments.sessions.get(candidateStatus.conversationId);
        if (current && current.active && current.transportMode === 'owner') {
            if (sessionMatchesActiveStatus(current, candidateStatus)) {
                current.status = 'streaming';
                current.countsAsStreaming = true;
                current.model = candidateStatus.modelId;
                const applicationResult = await inputArguments.ownerDispatch.applySnapshot(candidateStatus.conversationId, candidateStatus.requestId, assistantMessage, true);
                if (applicationResult === null) {
                    return skipCanonicalMessageLoad('active-stream', 'busy');
                }
                if (applicationResult === 'terminal') {
                    return requireCanonicalMessageLoad('terminalized-session', 'busy');
                }
                applyStatusPreviewSnapshot(candidateStatus, current.assistantMessage);
                inputArguments.runtime.notify(current, { type: 'replay' });
                return skipCanonicalMessageLoad('active-stream', 'busy');
            }
            if (activeStatusPrecedesSession(candidateStatus, current)) {
                return skipCanonicalMessageLoad('active-stream', 'busy');
            }
            releaseStaleOwnerSession(inputArguments, candidateStatus.conversationId, current);
        }
        applyStatusPreviewSnapshot(candidateStatus, assistantMessage);
        if (current && current.active && current.transportMode === 'follower') {
            if (sessionMatchesActiveStatus(current, candidateStatus)) {
                current.status = 'streaming';
                current.countsAsStreaming = true;
                current.model = candidateStatus.modelId;
                const applicationResult = await inputArguments.followerSessions.applyFollowerSnapshot(candidateStatus.conversationId, candidateStatus.requestId, assistantMessage, true);
                if (applicationResult === null) {
                    applyAssistantMessageSnapshot(current, assistantMessage);
                } else if (applicationResult === 'terminal') {
                    return requireCanonicalMessageLoad('terminalized-session', 'busy');
                }
                inputArguments.runtime.notify(current, { type: 'replay' });
                return skipCanonicalMessageLoad('active-stream', 'busy');
            }
            if (activeStatusPrecedesSession(candidateStatus, current)) {
                return skipCanonicalMessageLoad('active-stream', 'busy');
            }
            deactivateFollowerSession(inputArguments, candidateStatus.conversationId, current);
        }
        const session = createActiveFollowerSession(candidateStatus, assistantMessage);
        inputArguments.sessions.set(candidateStatus.conversationId, session);
        inputArguments.runtime.notify(session, { type: 'replay' });
        return skipCanonicalMessageLoad('active-stream', 'busy');
    }
    throw new Error('Chat stream status changed repeatedly during synchronization.');
};

const syncInactiveFollowerSnapshot = async (inputArguments: ActiveStatusFollowerSyncArguments, candidateStatus: ActiveChatStreamStatus, latestStatus: ChatStreamStatusSnapshot, assistantMessage: ChatStreamSession['assistantMessage']): Promise<ChatStreamMessageSavedReconciliation> => {
    if (latestStatus.active || latestStatus.startAdmission !== 'inactive') {
        return await reconcileInactiveStatusSnapshot(inputArguments, latestStatus);
    }
    const currentSession = inputArguments.sessions.get(candidateStatus.conversationId);
    if (currentSession && currentSession.transportMode === 'owner') {
        if (sessionMatchesActiveStatus(currentSession, candidateStatus)) {
            const reconciliation = resolveInactiveTerminalizationReconciliation(await finalizeInactiveOwnerSession(inputArguments, candidateStatus, currentSession, assistantMessage));
            if (reconciliation !== null) {
                return reconciliation;
            }
        } else if (activeStatusPrecedesSession(candidateStatus, currentSession)) {
            return skipCanonicalMessageLoad('active-stream', 'busy');
        } else if (currentSession.active) {
            releaseStaleOwnerSession(inputArguments, candidateStatus.conversationId, currentSession);
        } else {
            discardOwnerSession(inputArguments, candidateStatus.conversationId, currentSession);
        }
    }
    const currentAfterOwner = inputArguments.sessions.get(candidateStatus.conversationId);
    if (currentAfterOwner && currentAfterOwner.active && currentAfterOwner.transportMode === 'follower') {
        if (activeStatusPrecedesSession(candidateStatus, currentAfterOwner)) {
            return skipCanonicalMessageLoad('active-stream', 'busy');
        }
        if (sessionMatchesActiveStatus(currentAfterOwner, candidateStatus)) {
            const reconciliation = resolveInactiveTerminalizationReconciliation(await terminalizeInactiveFollower(inputArguments, latestStatus.conversationId, candidateStatus.requestId));
            if (reconciliation !== null) {
                return reconciliation;
            }
        } else {
            deactivateFollowerSession(inputArguments, candidateStatus.conversationId, currentAfterOwner);
        }
    }
    const terminalMessage = await waitForInactiveTerminalSnapshot(inputArguments, candidateStatus, assistantMessage, true);
    if (!inputArguments.isCurrent()) {
        return requireCanonicalMessageLoad('stale-generation');
    }
    if (terminalMessage === null) {
        const terminalSession = createActiveFollowerSession(candidateStatus, assistantMessage);
        inputArguments.sessions.set(candidateStatus.conversationId, terminalSession);
        const reconciliation = resolveInactiveTerminalizationReconciliation(await finalizeInactiveFollowerFromHydratedMessage(inputArguments, terminalSession, assistantMessage));
        return reconciliation ?? requireCanonicalMessageLoad();
    }
    const reconciliation = await reconcileCurrentSessionForTerminalSnapshot(inputArguments, candidateStatus, terminalMessage);
    if (reconciliation !== null) {
        return reconciliation;
    }
    const terminalSession = createActiveFollowerSession(candidateStatus, terminalMessage);
    inputArguments.sessions.set(candidateStatus.conversationId, terminalSession);
    return resolveInactiveTerminalizationReconciliation(await finalizeInactiveFollowerFromHydratedMessage(inputArguments, terminalSession, terminalMessage)) ?? requireCanonicalMessageLoad();
};

export { reconcileInactiveStatusSnapshot, syncActiveFollower };
