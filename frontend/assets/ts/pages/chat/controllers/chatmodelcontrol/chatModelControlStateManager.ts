/* SoAI - Chat page model control state manager [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import { isString } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { resolveNormalizedComparisonModelIdsFromModelSettings } from '@core/chat/comparisonModels.ts';
import type { Conversation } from '@features/chat/public.ts';

export type EffectiveModels = { primary: string | null; comparison: string[] };

export const normalizeChatModelId = (value: string | null): string | null => {
    if (!isString(value)) {
        return null;
    }
    const trimmed = value.trim();
    return trimmed ? trimmed : null;
};

export const resolveConversationPrimaryModelId = (conversation: Conversation | null): string | null => {
    if (!conversation) {
        return null;
    }
    const modelValue = conversation.modelSettings?.model;
    return isString(modelValue) ? normalizeChatModelId(modelValue) : null;
};

export const resolveEffectiveModelsForChatModelControl = (inputArguments: { conversation: Conversation | null; fallbackModelId: string | null }): EffectiveModels => {
    const conversationPrimary = resolveConversationPrimaryModelId(inputArguments.conversation);
    const primary = conversationPrimary ?? normalizeChatModelId(inputArguments.fallbackModelId);
    const comparison = resolveNormalizedComparisonModelIdsFromModelSettings({
        modelSettings: inputArguments.conversation?.modelSettings ?? null,
        primaryModelId: primary
    });
    return { primary, comparison };
};

export const resolveNextComparisonModelId = (inputArguments: { models: ModelData[]; primary: string; comparison: string[] }): string => {
    const selected = new Set<string>([inputArguments.primary, ...inputArguments.comparison]);
    for (const model of inputArguments.models) {
        if (!isChatSelectableModel(model)) {
            continue;
        }
        const candidate = normalizeChatModelId(model.id);
        if (!candidate) {
            continue;
        }
        if (selected.has(candidate)) {
            continue;
        }
        return candidate;
    }
    return inputArguments.primary;
};
