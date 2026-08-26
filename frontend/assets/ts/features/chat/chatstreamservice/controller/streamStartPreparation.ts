/* SoAI - Canonical stream-start validation and feedback resolution [frontend/assets/ts/features/chat/chatstreamservice/controller/streamStartPreparation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ChatMessage, ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';
import type { ContentPreviewFeedbackPayload, PreviewContractViolationFeedbackPayload } from '@features/chat/contentPreviewContracts.ts';
import { resolveLatestPendingContentPreviewFeedback, resolvePendingContentPreviewFeedback } from '@features/chat/contentPreviewFeedbackState.ts';
import { isPreviewContractReasonCode } from '@features/chat/preview/previewReferenceContract.ts';
import { PREVIEW_CONTRACT_VIOLATION_CODE, resolvePreviewContractViolationFeedback } from '@features/chat/previewContractViolationState.ts';
import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';

type ResolvedContentPreviewFeedback = {
    contentPreviewFeedback: ContentPreviewFeedbackPayload | null;
    contentPreviewFeedbackSourceMessage: ChatMessage | null;
};

const haveSameContentPreviewFeedbackPayload = (left: ContentPreviewFeedbackPayload, right: ContentPreviewFeedbackPayload): boolean => {
    if (left.assistantAtMs !== right.assistantAtMs || left.assistantTurnAtMs !== right.assistantTurnAtMs || left.items.length !== right.items.length) {
        return false;
    }
    for (let index = 0; index < left.items.length; index += 1) {
        const leftItem = left.items[index];
        const rightItem = right.items[index];
        if (!leftItem || !rightItem) {
            return false;
        }
        if (leftItem.referenceType !== rightItem.referenceType || leftItem.target !== rightItem.target || leftItem.status !== rightItem.status || leftItem.reasonCode !== rightItem.reasonCode) {
            return false;
        }
    }
    return true;
};

const requireContentPreviewFeedbackForStreamStart = (payload: ContentPreviewFeedbackPayload, sourceMessage: ChatMessage | null | undefined): ContentPreviewFeedbackPayload => {
    if (!sourceMessage) {
        throw new Error('Content preview feedback stream start requires a source assistant message');
    }
    const resolved = resolvePendingContentPreviewFeedback(sourceMessage);
    if (resolved === null || !haveSameContentPreviewFeedbackPayload(payload, resolved)) {
        throw new Error('Content preview feedback stream start payload does not match source assistant message');
    }
    return resolved;
};

const requirePreviewContractFeedbackForStreamStart = (payload: PreviewContractViolationFeedbackPayload): PreviewContractViolationFeedbackPayload => {
    const identity = resolveAssistantMessageIdentity({
        assistantTimestamp: payload.assistantAtMs,
        assistantTurnTimestamp: payload.assistantTurnAtMs,
        modelVariantIndex: 0
    });
    if (identity === null) {
        throw new Error('Preview contract feedback stream start payload has invalid assistant identity');
    }
    if (payload.code !== PREVIEW_CONTRACT_VIOLATION_CODE) {
        throw new Error('Preview contract feedback stream start payload has invalid code');
    }
    if (payload.reasonCode !== null && !isPreviewContractReasonCode(payload.reasonCode)) {
        throw new Error('Preview contract feedback stream start payload has invalid reason_code');
    }
    if (payload.detail !== null && (!isString(payload.detail) || !payload.detail.trim())) {
        throw new Error('Preview contract feedback stream start payload has invalid detail');
    }
    if (payload.repairAttempted !== true && payload.repairAttempted !== false) {
        throw new Error('Preview contract feedback stream start payload has invalid repair_attempted');
    }
    if (payload.repairSucceeded !== true && payload.repairSucceeded !== false) {
        throw new Error('Preview contract feedback stream start payload has invalid repair_succeeded');
    }
    return {
        assistantAtMs: identity.assistantTimestamp,
        assistantTurnAtMs: identity.assistantTurnTimestamp,
        code: PREVIEW_CONTRACT_VIOLATION_CODE,
        reasonCode: payload.reasonCode,
        detail: payload.detail === null ? null : payload.detail.trim(),
        repairAttempted: payload.repairAttempted,
        repairSucceeded: payload.repairSucceeded
    };
};

const resolveContentPreviewFeedbackForStreamStart = (conversation: ConversationContract, options: { contentPreviewFeedback?: ContentPreviewFeedbackPayload | null; contentPreviewFeedbackSourceMessage?: ChatMessage | null }): ResolvedContentPreviewFeedback => {
    if (options.contentPreviewFeedback !== undefined) {
        if (options.contentPreviewFeedback === null) {
            return {
                contentPreviewFeedback: null,
                contentPreviewFeedbackSourceMessage: null
            };
        }
        const sourceMessage = options.contentPreviewFeedbackSourceMessage ?? null;
        return {
            contentPreviewFeedback: requireContentPreviewFeedbackForStreamStart(options.contentPreviewFeedback, sourceMessage),
            contentPreviewFeedbackSourceMessage: sourceMessage
        };
    }
    const resolvedPending = resolveLatestPendingContentPreviewFeedback(conversation);
    return {
        contentPreviewFeedback: resolvedPending ? resolvedPending.feedback : null,
        contentPreviewFeedbackSourceMessage: resolvedPending ? resolvedPending.message : null
    };
};

const resolvePreviewContractFeedbackForStreamStart = (message: ConversationMessage | null | undefined, options: { previewContractFeedback?: PreviewContractViolationFeedbackPayload | null }): PreviewContractViolationFeedbackPayload | null => {
    if (options.previewContractFeedback !== undefined) {
        return options.previewContractFeedback === null ? null : requirePreviewContractFeedbackForStreamStart(options.previewContractFeedback);
    }
    return resolvePreviewContractViolationFeedback(message);
};

export { resolveContentPreviewFeedbackForStreamStart, resolvePreviewContractFeedbackForStreamStart };
export type { ResolvedContentPreviewFeedback };
