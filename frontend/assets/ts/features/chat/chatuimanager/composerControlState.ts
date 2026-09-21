/* SoAI - Chat UI manager composer action and send readiness state [frontend/assets/ts/features/chat/chatuimanager/composerControlState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { isChatAttachmentReadyForSend } from '@features/chat/ChatAttachmentSupport.ts';
import { getElement } from '@features/chat/chatuimanager/dom.ts';
import type { ChatComposerActionMode, ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import type { ChatStreamLifecycle, ChatTurnAdmissionSnapshot } from '@features/chat/chatstreamservice/types.ts';
import { resolveNormalizedComparisonModelIdsFromModelSettings } from '@core/chat/comparisonModels.ts';
import { isClaimableKnowledgeDraft } from '@features/chat/knowledgeAttachmentReadiness.ts';
import { preflightChatExecutionModelSelection, preflightChatExecutionModels } from '@features/chat/modelExecutionPreflight.ts';

interface ChatComposerPayloadState {
    hasText: boolean;
    hasReadyAttachments: boolean;
    hasKnowledgeDraft: boolean;
}

export interface ChatComposerControlState {
    isExecuting: boolean;
    isChatStreaming: boolean;
    streamLifecycle: ChatStreamLifecycle;
    actionMode: ChatComposerActionMode;
    hasText: boolean;
    canStop: boolean;
    canSend: boolean;
    canQueue: boolean;
}

const resolveConversationExecutionState = (context: ChatUIManagerContext, conversationId: string): boolean => {
    if (!conversationId) {
        return false;
    }
    return context.dependencies.session.isConversationExecuting(conversationId);
};

const resolveTurnAdmissionState = (context: ChatUIManagerContext, conversationId: string): ChatTurnAdmissionSnapshot => {
    if (!conversationId) {
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
    return context.dependencies.session.getTurnAdmission(conversationId);
};

const conversationHasComparisonModels = (context: ChatUIManagerContext): boolean => {
    const conversation = context.dependencies.session.getCurrentConversation();
    if (!conversation || !isObject(conversation)) {
        return false;
    }
    const settings = conversation.modelSettings;
    if (!settings) {
        return false;
    }
    const primaryValue = context.dependencies.session.getCurrentModel();
    const resolvedPrimaryValue = toTrimmedString(primaryValue);
    const resolvedPrimary = resolvedPrimaryValue ? resolvedPrimaryValue : null;
    const conversationPrimaryValue = settings.model;
    const conversationPrimaryText = toTrimmedString(conversationPrimaryValue);
    const conversationPrimary = conversationPrimaryText ? conversationPrimaryText : null;
    const primary = resolvedPrimary ?? conversationPrimary;
    const comparison = resolveNormalizedComparisonModelIdsFromModelSettings({ modelSettings: settings, primaryModelId: primary });
    return comparison.length > 0;
};

const resolveHasStreamingComparisonModels = (context: ChatUIManagerContext, conversationId: string): boolean => {
    const fromSettings = conversationHasComparisonModels(context);
    const hasActiveComparisonRun = conversationId ? context.dependencies.session.hasActiveComparisonRun(conversationId) : false;
    return hasActiveComparisonRun || fromSettings;
};

const resolveButtonMode = (admission: ChatTurnAdmissionSnapshot, hasText: boolean, hasReadyAttachments: boolean, hasComparisonModels: boolean): ChatComposerActionMode => {
    const hasPayload = hasText || hasReadyAttachments;
    if (admission.phase === 'inactive') {
        return 'send';
    }
    if (admission.phase === 'stopping' || admission.phase === 'stop_failed' || admission.phase === 'terminalizing') {
        return 'stop';
    }
    if (!hasPayload) {
        return admission.canStop ? 'stop' : 'send';
    }
    if (admission.canSteerPrompt && !hasComparisonModels) {
        return 'steer';
    }
    if (admission.canQueuePrompt) {
        return 'queue';
    }
    return 'send';
};

const resolveCanSendWithSelectedModels = (context: ChatUIManagerContext): boolean => {
    const selectedModelValue = context.dependencies.session.getCurrentModel();
    const selectedModelText = toTrimmedString(selectedModelValue);
    const selectedModelId = selectedModelText ? selectedModelText : null;
    const conversation = context.dependencies.session.getCurrentConversation();
    if (!conversation || !isObject(conversation)) {
        return (
            preflightChatExecutionModelSelection({
                selectedModelId,
                modelStreamHasPayload: context.dependencies.session.getModelStreamHasPayload(),
                isModelAvailable: (modelId) => context.dependencies.session.isModelAvailable(modelId)
            }).status === 'ok'
        );
    }
    const preflight = preflightChatExecutionModels({
        conversation,
        selectedModelId,
        modelStreamHasPayload: context.dependencies.session.getModelStreamHasPayload(),
        isModelAvailable: (modelId) => context.dependencies.session.isModelAvailable(modelId)
    });
    return preflight.status === 'ok';
};

const resolveComposerPayloadState = (context: ChatUIManagerContext): ChatComposerPayloadState => {
    const input = getElement(context, 'input');
    const inputElement = input instanceof HTMLTextAreaElement ? input : null;
    const hasText = inputElement ? readTrimmedInputValue(inputElement).length > 0 : false;
    const attachments = context.dependencies.drafts.getAttachments();
    const hasReadyAttachments = isArray(attachments) && attachments.some((attachment) => isChatAttachmentReadyForSend(attachment));
    const draftItems = context.dependencies.drafts.getDraftKnowledgeAttachments();
    const hasKnowledgeDraft = isArray(draftItems) && draftItems.some(isClaimableKnowledgeDraft);
    return { hasText, hasReadyAttachments, hasKnowledgeDraft };
};

const resolveComposerReadiness = (context: ChatUIManagerContext, payload: ChatComposerPayloadState, isExecuting: boolean, admission: ChatTurnAdmissionSnapshot): { canSend: boolean; canQueue: boolean } => {
    const canAttemptSend = !isExecuting;
    const canAttemptQueue = admission.canQueuePrompt || admission.canSteerPrompt;
    const hasPayload = payload.hasText || payload.hasReadyAttachments || payload.hasKnowledgeDraft;
    if (!canAttemptSend && !canAttemptQueue) {
        return { canSend: false, canQueue: false };
    }
    const hasPendingAttachmentProcessing = context.dependencies.session.hasPendingAttachmentProcessing();
    const canSendWithSelectedModels = resolveCanSendWithSelectedModels(context);
    const isReady = hasPayload && !hasPendingAttachmentProcessing && canSendWithSelectedModels;
    return {
        canSend: canAttemptSend && isReady,
        canQueue: canAttemptQueue && isReady
    };
};

export const resolveComposerControlState = (context: ChatUIManagerContext): ChatComposerControlState => {
    const conversationId = toTrimmedString(context.dependencies.session.getCurrentConversationId());
    const isExecuting = resolveConversationExecutionState(context, conversationId);
    const admission = resolveTurnAdmissionState(context, conversationId);
    const isChatStreaming = admission.localUiActive || admission.backendActive;
    const streamLifecycle = admission.streamLifecycle;
    const isTokenStreaming = admission.phase === 'streaming';
    const payload = resolveComposerPayloadState(context);
    const readiness = resolveComposerReadiness(context, payload, isExecuting, admission);
    const hasReadyPayload = payload.hasReadyAttachments || payload.hasKnowledgeDraft;
    const hasComparisonModels = isTokenStreaming ? resolveHasStreamingComparisonModels(context, conversationId) : false;
    const actionMode = resolveButtonMode(admission, payload.hasText, hasReadyPayload, hasComparisonModels);
    return {
        isExecuting,
        isChatStreaming,
        streamLifecycle,
        actionMode,
        hasText: payload.hasText,
        canStop: admission.canStop,
        canSend: readiness.canSend,
        canQueue: readiness.canQueue
    };
};
