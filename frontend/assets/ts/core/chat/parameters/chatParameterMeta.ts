/* SoAI - Shared chat parameter meta [frontend/assets/ts/core/chat/parameters/chatParameterMeta.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameterMeta } from '@core/chat/parameters/types.ts';
import { MAX_AGENT_MAX_ITERATIONS } from '@core/chat/parameters/agentMaxIterations.ts';
import { CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN } from '@core/chat/parameters/textZoom.ts';

const CHAT_PARAMETER_META: Readonly<Record<string, ChatParameterMeta>> = Object.freeze({
    temperature: { type: 'number', precision: 1, min: 0, max: 2 },
    contextWindowTokens: { type: 'number', precision: 0, min: 1 },
    maxCompletionTokens: { type: 'number', precision: 0, min: 0 },
    topP: { type: 'number', precision: 2, min: 0, max: 1 },
    frequencyPenalty: { type: 'number', precision: 1, min: -2, max: 2 },
    presencePenalty: { type: 'number', precision: 1, min: -2, max: 2 },
    topLogprobs: { type: 'number', precision: 0, min: 0, max: 5 },
    completionCount: { type: 'number', precision: 0, min: 1, max: 128 },
    textZoom: { type: 'number', precision: 1, min: CHAT_TEXT_ZOOM_MIN, max: CHAT_TEXT_ZOOM_MAX },
    agentMaxIterations: { type: 'number', precision: 0, min: 1, max: MAX_AGENT_MAX_ITERATIONS }
});

const getParameterMeta = (parameter: string): ChatParameterMeta | null => {
    const meta = CHAT_PARAMETER_META[parameter];
    return meta ? meta : null;
};

export { CHAT_PARAMETER_META, getParameterMeta };
