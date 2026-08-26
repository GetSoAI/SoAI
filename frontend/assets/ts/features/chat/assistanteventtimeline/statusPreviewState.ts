/* SoAI - Chat feature status preview state [frontend/assets/ts/features/chat/assistanteventtimeline/statusPreviewState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isObject, isPositiveInteger, isString } from '@core/typeGuards.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

interface StatusPreviewDomState {
    hasPreview: boolean;
    text: string;
    cooldownMs: number;
}

const resolveStatusPreviewDomStateFromMessage = (message: ChatMessage): StatusPreviewDomState => {
    if (!isObject(message)) {
        return { hasPreview: false, text: '', cooldownMs: 0 };
    }
    const textValue = message.streamStatusPreviewText;
    if (!isString(textValue)) {
        return { hasPreview: false, text: '', cooldownMs: 0 };
    }
    const trimmed = textValue.trim();
    if (!trimmed) {
        return { hasPreview: false, text: '', cooldownMs: 0 };
    }
    const cooldownValue = message.streamStatusPreviewCooldownMs;
    if (!isPositiveInteger(cooldownValue)) {
        throw new Error('Streaming status preview requires a positive cooldown.');
    }
    return { hasPreview: true, text: trimmed, cooldownMs: cooldownValue };
};

export { resolveStatusPreviewDomStateFromMessage };
export type { StatusPreviewDomState };
