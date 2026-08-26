/* SoAI - Chat feature comparison turn metadata [frontend/assets/ts/features/chat/comparisonTurnMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { requireAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';

type ChatComparisonTurnInvalidReason = 'missing_canonical_variant' | 'duplicate_variant_index' | 'non_contiguous_variant_indexes';

interface ChatComparisonTurnMeta {
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
}

interface ChatComparisonTurnState {
    comparisonVariantTotal: number;
    invalidReason: ChatComparisonTurnInvalidReason | null;
}

const resolveNonNegativeInteger = (value: JsonValue | undefined, fieldName: string): number | null => {
    if (value === undefined || value === null) {
        return null;
    }
    const resolved = readNonNegativeIntegerOrNullValue(value);
    if (resolved === null) {
        throw new Error(`Chat message ${fieldName} must be a non-negative integer when provided`);
    }
    return resolved;
};

const resolveChatComparisonTurnMeta = (message: ChatMessage): ChatComparisonTurnMeta | null => {
    const assistantTurnTimestamp = resolveNonNegativeInteger(message.assistantTurnAtMs, 'assistant_turn_at_ms');
    const modelVariantIndex = resolveNonNegativeInteger(message.modelVariantIndex, 'model_variant_index');
    if (message.role !== 'assistant') {
        if (assistantTurnTimestamp !== null || modelVariantIndex !== null) {
            throw new Error('Only assistant messages may define comparison-turn metadata');
        }
        return null;
    }
    if (assistantTurnTimestamp === null || modelVariantIndex === null) {
        throw new Error('Assistant messages must define assistant_turn_at_ms and model_variant_index');
    }
    requireAssistantMessageIdentity({
        assistantTimestamp: message.timestamp,
        assistantTurnTimestamp,
        modelVariantIndex,
        context: 'Assistant message'
    });
    return {
        assistantTurnTimestamp,
        modelVariantIndex
    };
};

const buildComparisonTurnState = (inputArguments: { hasDuplicateVariantIndex: boolean; variantIndexes: ReadonlySet<number> }): ChatComparisonTurnState => {
    if (inputArguments.hasDuplicateVariantIndex) {
        return {
            comparisonVariantTotal: 1,
            invalidReason: 'duplicate_variant_index'
        };
    }
    if (!inputArguments.variantIndexes.has(0)) {
        return {
            comparisonVariantTotal: 1,
            invalidReason: 'missing_canonical_variant'
        };
    }
    const highestVariantIndex = Math.max(...inputArguments.variantIndexes);
    for (let expectedVariantIndex = 0; expectedVariantIndex <= highestVariantIndex; expectedVariantIndex += 1) {
        if (!inputArguments.variantIndexes.has(expectedVariantIndex)) {
            return {
                comparisonVariantTotal: 1,
                invalidReason: 'non_contiguous_variant_indexes'
            };
        }
    }
    return {
        comparisonVariantTotal: highestVariantIndex + 1,
        invalidReason: null
    };
};

const resolveComparisonTurnStatesByTurn = (metadata: readonly (ChatComparisonTurnMeta | null)[]): Map<number, ChatComparisonTurnState> => {
    const variantIndexesByTurn = new Map<number, { hasDuplicateVariantIndex: boolean; variantIndexes: Set<number> }>();
    for (const meta of metadata) {
        if (meta === null) {
            continue;
        }
        const existing = variantIndexesByTurn.get(meta.assistantTurnTimestamp);
        if (existing) {
            if (existing.variantIndexes.has(meta.modelVariantIndex)) {
                existing.hasDuplicateVariantIndex = true;
            }
            existing.variantIndexes.add(meta.modelVariantIndex);
            continue;
        }
        variantIndexesByTurn.set(meta.assistantTurnTimestamp, {
            hasDuplicateVariantIndex: false,
            variantIndexes: new Set([meta.modelVariantIndex])
        });
    }
    const statesByTurn = new Map<number, ChatComparisonTurnState>();
    for (const [assistantTurnTimestamp, state] of variantIndexesByTurn.entries()) {
        statesByTurn.set(assistantTurnTimestamp, buildComparisonTurnState(state));
    }
    return statesByTurn;
};

const isComparisonOnlyAssistantVariant = (message: ChatMessage): boolean => {
    const meta = resolveChatComparisonTurnMeta(message);
    return meta !== null && meta.modelVariantIndex > 0;
};

export { isComparisonOnlyAssistantVariant, resolveChatComparisonTurnMeta, resolveComparisonTurnStatesByTurn };
export type { ChatComparisonTurnMeta, ChatComparisonTurnState };
export type { ChatComparisonTurnInvalidReason };
