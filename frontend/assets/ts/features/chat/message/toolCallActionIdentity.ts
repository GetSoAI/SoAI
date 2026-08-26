/* SoAI - Chat tool call action identity parsing [frontend/assets/ts/features/chat/message/toolCallActionIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseNonNegativeIntegerFromStringOrNull } from '@core/dom/attributes.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChatMessageActionData } from '@features/chat/message/actionDeps.ts';
import { resolveAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';

interface ToolCallActionIdentity {
    assistantTurnAtMs: number;
    modelVariantIndex: number;
    toolCallId: string;
}

const parseActionIntegerText = (value: string | null | undefined): number | null => {
    if (!isString(value) || !value.trim()) {
        return null;
    }
    return parseNonNegativeIntegerFromStringOrNull(value.trim());
};

const resolveToolCallActionIdentity = (data: ChatMessageActionData | undefined): ToolCallActionIdentity | null => {
    const toolCallId = isString(data?.callId) && data.callId.trim() ? data.callId.trim() : '';
    const assistantIdentity = resolveAssistantVariantIdentity({
        assistantTurnTimestamp: parseActionIntegerText(data?.assistantTurnTs),
        modelVariantIndex: parseActionIntegerText(data?.modelVariantIndex)
    });
    if (!toolCallId || assistantIdentity === null) {
        return null;
    }
    return {
        assistantTurnAtMs: assistantIdentity.assistantTurnTimestamp,
        modelVariantIndex: assistantIdentity.modelVariantIndex,
        toolCallId
    };
};

export { resolveToolCallActionIdentity };
export type { ToolCallActionIdentity };
