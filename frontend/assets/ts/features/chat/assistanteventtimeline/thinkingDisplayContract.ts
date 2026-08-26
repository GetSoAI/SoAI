/* SoAI - Chat feature thinking display contract [frontend/assets/ts/features/chat/assistanteventtimeline/thinkingDisplayContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ThinkingTimelineItem } from '@features/chat/ChatTypes.ts';

interface ThinkingDisplayContract {
    prefaceText: string | null;
    thinkingText: string;
    renderThinkingActivity: boolean;
}

const normalizeInlineText = (value: string): string => value.replace(/\s+/g, ' ').trim();

const resolveThinkingDisplayContract = (phase: ThinkingTimelineItem): ThinkingDisplayContract => {
    const prefaceText = isString(phase.prefaceText) ? phase.prefaceText.trim() : '';
    if (phase.renderMode === 'thinking_only') {
        return {
            prefaceText: null,
            thinkingText: phase.text,
            renderThinkingActivity: true
        };
    }
    if (!prefaceText) {
        throw new Error(`Thinking phase ${phase.phaseId} is missing preface_text.`);
    }
    return {
        prefaceText: normalizeInlineText(prefaceText),
        thinkingText: phase.text,
        renderThinkingActivity: phase.renderMode !== 'preface_only'
    };
};

export { resolveThinkingDisplayContract };
export type { ThinkingDisplayContract };
