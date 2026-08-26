/* SoAI - Assistant preview-contract violation extraction for regeneration retries [frontend/assets/ts/features/chat/previewContractViolationState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isString } from '@core/typeGuards.ts';
import type { ConversationMessage } from '@features/chat/ChatTypes.ts';
import type { PreviewContractViolationFeedbackPayload } from '@features/chat/contentPreviewContracts.ts';
import { isCanonicalAssistantMessage } from '@features/chat/contentPreviewFeedbackState.ts';
import { resolvePreviewContractPayload } from '@features/chat/previewContractState.ts';
import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';

const PREVIEW_CONTRACT_VIOLATION_CODE: PreviewContractViolationFeedbackPayload['code'] = 'preview_contract_violation';

const resolvePreviewContractViolationFeedback = (message: ConversationMessage | null | undefined): PreviewContractViolationFeedbackPayload | null => {
    if (!isCanonicalAssistantMessage(message)) {
        return null;
    }
    const timeline = message.assistantEventTimeline;
    if (!isArray(timeline)) {
        return null;
    }
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const candidate = timeline[index];
        if (!candidate) {
            continue;
        }
        if (candidate.eventType !== 'error') {
            continue;
        }
        const code = candidate.payload.code;
        if (!isString(code) || code.trim() !== PREVIEW_CONTRACT_VIOLATION_CODE) {
            continue;
        }
        const identity = resolveAssistantMessageIdentity({
            assistantTimestamp: message.timestamp,
            assistantTurnTimestamp: message.assistantTurnAtMs,
            modelVariantIndex: message.modelVariantIndex
        });
        if (identity === null) {
            return null;
        }
        const previewContract = resolvePreviewContractPayload(candidate.payload.previewContract);
        return {
            assistantAtMs: identity.assistantTimestamp,
            assistantTurnAtMs: identity.assistantTurnTimestamp,
            code: PREVIEW_CONTRACT_VIOLATION_CODE,
            reasonCode: previewContract?.reasonCode ?? null,
            detail: previewContract?.detail ?? null,
            repairAttempted: previewContract?.repairAttempted === true,
            repairSucceeded: previewContract?.repairSucceeded === true
        };
    }
    return null;
};

export { PREVIEW_CONTRACT_VIOLATION_CODE, resolvePreviewContractViolationFeedback };
