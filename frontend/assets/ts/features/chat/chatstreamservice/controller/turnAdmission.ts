/* SoAI - Chat turn admission snapshot resolution [frontend/assets/ts/features/chat/chatstreamservice/controller/turnAdmission.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getConversationStreamState, isConversationStreamingUiActive, reconcileInactiveSyncedConversation } from '@features/chat/chatstreamservice/controller/state.ts';
import { waitForTerminalReconciliation } from '@features/chat/chatstreamservice/controller/terminalizationState.ts';
import type { ChatStreamingControllerContext, StreamLifecyclePhase } from '@features/chat/chatstreamservice/controller/types.ts';
import type { ChatStreamLifecycle, ChatStreamStartAdmission, ChatTurnAdmissionPhase, ChatTurnAdmissionSnapshot } from '@features/chat/chatstreamservice/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const resolvePhase = (inputArguments: { streamLifecycle: ChatStreamLifecycle; canQueue: boolean; canStart: boolean; localUiActive: boolean; localPhase: StreamLifecyclePhase | null }): ChatTurnAdmissionPhase => {
    if (inputArguments.localPhase === 'stopping') {
        return 'stopping';
    }
    if (inputArguments.localPhase === 'stop_failed') {
        return 'stop_failed';
    }
    if (inputArguments.streamLifecycle === 'terminalizing') {
        return 'terminalizing';
    }
    if (inputArguments.localPhase === 'terminalizing') {
        return 'terminalizing';
    }
    if (inputArguments.streamLifecycle === 'streaming') {
        return 'streaming';
    }
    if (inputArguments.canQueue && !inputArguments.canStart) {
        return 'reserved';
    }
    if (inputArguments.localUiActive) {
        return 'starting';
    }
    return 'inactive';
};

const buildTurnAdmissionSnapshot = (context: ChatStreamingControllerContext, conversationId: string): ChatTurnAdmissionSnapshot => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return {
            conversationId: '',
            phase: 'inactive',
            backendActive: false,
            localUiActive: false,
            activeStreamIdentity: null,
            canStop: false,
            canSendNow: false,
            canQueuePrompt: false,
            canSteerPrompt: false,
            streamLifecycle: 'inactive',
            startAdmission: 'unknown'
        };
    }
    const streamLifecycle = context.dependencies.chatStreamService.getStreamLifecycle(normalizedConversationId);
    const activeStreamIdentity = context.dependencies.chatStreamService.getStreamIdentity(normalizedConversationId);
    const canQueue = context.dependencies.chatStreamService.canQueueConversationInput(normalizedConversationId);
    const canSteer = context.dependencies.chatStreamService.canSteerConversationInput(normalizedConversationId);
    const canStart = context.dependencies.chatStreamService.canStartPromptNow(normalizedConversationId);
    const localUiActive = isConversationStreamingUiActive(context, normalizedConversationId);
    const localPhase = getConversationStreamState(context, normalizedConversationId)?.phase ?? null;
    const backendActive = streamLifecycle !== 'inactive';
    const phase = resolvePhase({ streamLifecycle, canQueue, canStart, localUiActive, localPhase });
    const startAdmission: ChatStreamStartAdmission = canStart && phase === 'inactive' ? 'inactive' : phase === 'inactive' ? 'unknown' : 'busy';
    return {
        conversationId: normalizedConversationId,
        phase,
        backendActive,
        localUiActive,
        activeStreamIdentity,
        canStop: phase === 'starting' || phase === 'streaming' || phase === 'stop_failed',
        canSendNow: phase === 'inactive' && canStart,
        canQueuePrompt: phase === 'streaming' || phase === 'stop_failed' || phase === 'stopping' || phase === 'terminalizing' || phase === 'reserved',
        canSteerPrompt: phase === 'streaming' && canSteer,
        streamLifecycle,
        startAdmission
    };
};

const resolveSyncedTurnAdmissionSnapshot = async (context: ChatStreamingControllerContext, conversationId: string, signal?: AbortSignal | null): Promise<ChatTurnAdmissionSnapshot> => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return buildTurnAdmissionSnapshot(context, '');
    }
    await waitForTerminalReconciliation(context, normalizedConversationId, signal ?? null);
    const reconciliation = await context.dependencies.chatStreamService.syncConversationStatus(normalizedConversationId);
    if (reconciliation.startAdmission === 'inactive') {
        reconcileInactiveSyncedConversation(context, normalizedConversationId);
    }
    const snapshot = buildTurnAdmissionSnapshot(context, normalizedConversationId);
    if (snapshot.phase === 'inactive') {
        return {
            ...snapshot,
            startAdmission: reconciliation.startAdmission,
            canSendNow: reconciliation.startAdmission === 'inactive'
        };
    }
    return snapshot;
};

export { buildTurnAdmissionSnapshot, resolveSyncedTurnAdmissionSnapshot };
