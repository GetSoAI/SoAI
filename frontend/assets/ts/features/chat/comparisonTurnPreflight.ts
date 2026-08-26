/* SoAI - Comparison-turn preflight response parsing [frontend/assets/ts/features/chat/comparisonTurnPreflight.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { trimStringList } from '@core/normalize.ts';
import type { ComparisonTurnPreflightRequest, ComparisonTurnPreflightResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { requireAssistantMessageIdentity, requireNonNegativeModelVariantIndex, requirePositiveEpochMs } from '@core/chat/assistantIdentity.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ComparisonTurnPreflightVariant = {
    modelVariantIndex: number;
    requestedModelId: string;
    resolvedModelId: string;
    assistantTimestamp: number;
};

type ComparisonTurnPreflightResult = {
    assistantTurnTimestamp: number;
    variants: ComparisonTurnPreflightVariant[];
};

interface ComparisonTurnPreflightApiClient {
    webui: {
        chat: {
            comparisonTurns: {
                preflight(conversationId: string, request: ComparisonTurnPreflightRequest): Promise<ComparisonTurnPreflightResponse>;
            };
        };
    };
}

const resolveMinimumAssistantTurnAtMs = (value: number | null | undefined): number | null => {
    if (value === undefined || value === null) {
        return null;
    }
    if (typeof value !== 'number' || !isEpochMsNumber(value)) {
        throw new Error('Comparison preflight minimum assistant turn timestamp must be an epoch-millisecond integer');
    }
    return value;
};

const normalizePreflightVariant = (response: ComparisonTurnPreflightResponse['variants'][number]): ComparisonTurnPreflightVariant => {
    const modelVariantIndex = requireNonNegativeModelVariantIndex(response.modelVariantIndex, 'Comparison preflight response variants[].model_variant_index');
    const assistantTimestamp = requirePositiveEpochMs(response.assistantAtMs, 'Comparison preflight response variants[].assistant_at_ms');
    const requestedModelId = response.requestedModelId;
    const resolvedModelId = response.resolvedModelId;
    return { modelVariantIndex, requestedModelId, resolvedModelId, assistantTimestamp };
};

export const preflightComparisonTurn = async (apiClient: ComparisonTurnPreflightApiClient, inputArguments: { conversationId: string; primaryModelId: string; comparisonModelIds: string[]; minimumAssistantTurnAtMs?: number | null }): Promise<ComparisonTurnPreflightResult> => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    if (!conversationId) {
        throw new Error('Comparison preflight requires a conversationId');
    }
    const primaryModelId = inputArguments.primaryModelId.trim();
    if (!primaryModelId) {
        throw new Error('Comparison preflight requires a primaryModelId');
    }
    const comparisonModelIds = trimStringList(inputArguments.comparisonModelIds);
    const minimumAssistantTurnAtMs = resolveMinimumAssistantTurnAtMs(inputArguments.minimumAssistantTurnAtMs);
    const response = await apiClient.webui.chat.comparisonTurns.preflight(conversationId, {
        primaryModelId: primaryModelId,
        comparisonModelIds: comparisonModelIds,
        ...(minimumAssistantTurnAtMs === null ? {} : { minimumAssistantTurnAtMs: minimumAssistantTurnAtMs })
    });
    const assistantTurnTimestamp = requirePositiveEpochMs(response.assistantTurnAtMs, 'Comparison preflight response assistant_turn_at_ms');
    const variants = response.variants.map(normalizePreflightVariant);
    if (variants.length < 1) {
        throw new Error('Comparison preflight response requires at least one variant');
    }
    for (let index = 0; index < variants.length; index += 1) {
        const variant = variants[index] ?? null;
        if (!variant) {
            throw new Error('Comparison preflight response variants are missing required entries');
        }
        if (variant.modelVariantIndex !== index) {
            throw new Error('Comparison preflight response variants must be contiguous starting at 0');
        }
        requireAssistantMessageIdentity({
            assistantTimestamp: variant.assistantTimestamp,
            assistantTurnTimestamp,
            modelVariantIndex: variant.modelVariantIndex,
            context: 'Comparison preflight response variant'
        });
    }
    return { assistantTurnTimestamp, variants };
};

export type { ComparisonTurnPreflightResult, ComparisonTurnPreflightVariant };
