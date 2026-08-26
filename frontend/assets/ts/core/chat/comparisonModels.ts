/* SoAI - Canonical Chat comparison model selection [frontend/assets/ts/core/chat/comparisonModels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isString } from '@core/typeGuards.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';

const CHAT_COMPARISON_MAX_EFFECTIVE_MODELS = 5;

export const normalizeComparisonModelIds = (inputArguments: { primaryModelId: string | null; raw: JsonValue | null | undefined }): string[] => {
    if (inputArguments.raw === undefined || inputArguments.raw === null) {
        return [];
    }

    const primaryCandidate = isString(inputArguments.primaryModelId) ? inputArguments.primaryModelId.trim() : '';
    if (!isArray(inputArguments.raw)) {
        throw new Error('Chat comparison_models must be an array when provided');
    }
    if (!primaryCandidate) {
        if (inputArguments.raw.length === 0) {
            return [];
        }
        throw new Error('Chat comparison_models require a primary model');
    }

    const maxComparison = CHAT_COMPARISON_MAX_EFFECTIVE_MODELS - 1;

    const normalized: string[] = [];
    for (const entry of inputArguments.raw) {
        if (!isString(entry)) {
            throw new Error('Chat comparison model ids must be non-empty strings');
        }
        const trimmed = entry.trim();
        if (!trimmed) {
            throw new Error('Chat comparison model ids must be non-empty strings');
        }
        normalized.push(trimmed);
        if (normalized.length > maxComparison) {
            throw new Error(`Chat comparison models support at most ${String(maxComparison)} entries`);
        }
    }
    return normalized;
};

export const resolveNormalizedComparisonModelIdsFromModelSettings = (inputArguments: { modelSettings: ConversationModelSettings | null | undefined; primaryModelId: string | null }): string[] => {
    const comparisonModels = inputArguments.modelSettings?.comparisonModels;
    if (comparisonModels === undefined) {
        return [];
    }
    return normalizeComparisonModelIds({ primaryModelId: inputArguments.primaryModelId, raw: comparisonModels });
};

export { CHAT_COMPARISON_MAX_EFFECTIVE_MODELS };
