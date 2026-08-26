/* SoAI - Frontend token usage wire contracts [frontend/assets/ts/core/api/contracts/tokenUsageContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isFiniteNumber, isNonNegativeInteger, isObject, isPositiveInteger, isString } from '@core/typeGuards.ts';

interface TokenUsageSnapshot {
    promptTokens: number;
    promptOccupancyTokens: number;
    completionTokens: number;
    contextCompletionTokens: number;
    contextOccupancyTokens: number;
    totalTokens: number;
    contextWindowTokens: number | null;
    completionRateTokensPerSecond: number;
    source: string;
    contextWindowUnverified: boolean;
    precision: 'exact' | 'estimated';
    promptTokensCapped: boolean;
    promptTokensCappedReason: string | null;
    previewRevision: number | null;
}

const resolveTokenUsageVisibleContextWindowTokens = (usage: TokenUsageSnapshot): number | null => (usage.contextWindowTokens !== null && isPositiveInteger(usage.contextWindowTokens) ? usage.contextWindowTokens : null);
const tokenUsageHasEstimatedCurrentTokens = (usage: TokenUsageSnapshot): boolean => usage.source === 'estimate' || usage.source === 'reconstructed_transcript' || usage.source === 'aggregate_reconstructed_transcript' || usage.source === 'aggregate_mixed' || usage.precision === 'estimated' || usage.promptTokensCapped;
const tokenUsageHasEstimatedContextWindow = (usage: TokenUsageSnapshot): boolean => usage.contextWindowUnverified && resolveTokenUsageVisibleContextWindowTokens(usage) !== null;

const parseTokenUsageSnapshot = (value: JsonValue | null | undefined): TokenUsageSnapshot | null => {
    if (!isObject(value)) return null;
    const promptTokens = isNonNegativeInteger(value['prompt_tokens']) ? value['prompt_tokens'] : null;
    const promptOccupancyTokens = isNonNegativeInteger(value['prompt_occupancy_tokens']) ? value['prompt_occupancy_tokens'] : null;
    const completionTokens = isNonNegativeInteger(value['completion_tokens']) ? value['completion_tokens'] : null;
    const contextCompletionTokens = isNonNegativeInteger(value['context_completion_tokens']) ? value['context_completion_tokens'] : null;
    const contextOccupancyTokens = isNonNegativeInteger(value['context_occupancy_tokens']) ? value['context_occupancy_tokens'] : null;
    const totalTokens = isNonNegativeInteger(value['total_tokens']) ? value['total_tokens'] : null;
    const completionRateTokensPerSecond = isFiniteNumber(value['completion_rate_tokens_per_second']) && value['completion_rate_tokens_per_second'] >= 0 ? value['completion_rate_tokens_per_second'] : null;
    if (promptTokens === null || promptOccupancyTokens === null || completionTokens === null || contextCompletionTokens === null || contextOccupancyTokens === null || totalTokens === null || completionRateTokensPerSecond === null) return null;
    if (totalTokens !== promptTokens + completionTokens || contextOccupancyTokens !== promptOccupancyTokens + contextCompletionTokens || contextCompletionTokens > completionTokens || !hasOwn(value, 'context_window_tokens')) return null;
    const contextWindowRaw = value['context_window_tokens'];
    const contextWindowTokens = contextWindowRaw === null ? null : isPositiveInteger(contextWindowRaw) ? contextWindowRaw : null;
    if (contextWindowTokens === null && contextWindowRaw !== null) return null;
    const precisionRaw = value['precision'];
    if (precisionRaw !== 'exact' && precisionRaw !== 'estimated') return null;
    const sourceRaw = value['source'];
    const source = isString(sourceRaw) && sourceRaw.trim() ? sourceRaw.trim() : null;
    if (source === null) return null;
    const promptTokensCapped = value['prompt_tokens_capped'] === true;
    const cappedReasonRaw = value['prompt_tokens_capped_reason'];
    const promptTokensCappedReason = isString(cappedReasonRaw) && cappedReasonRaw.trim() ? cappedReasonRaw.trim() : null;
    if (promptTokensCapped && promptTokensCappedReason === null) return null;
    const previewRevisionRaw = value['preview_revision'];
    if (previewRevisionRaw !== null && previewRevisionRaw !== undefined && !isNonNegativeInteger(previewRevisionRaw)) return null;
    return { promptTokens, promptOccupancyTokens, completionTokens, contextCompletionTokens, contextOccupancyTokens, totalTokens, contextWindowTokens, completionRateTokensPerSecond, source, contextWindowUnverified: value['context_window_unverified'] === true, precision: precisionRaw, promptTokensCapped, promptTokensCappedReason, previewRevision: previewRevisionRaw ?? null };
};

const decodeTokenUsageSnapshot = (value: JsonValue): TokenUsageSnapshot => {
    const decoded = parseTokenUsageSnapshot(value);
    if (decoded === null) throw new TypeError('Token usage snapshot is invalid');
    return decoded;
};

export { decodeTokenUsageSnapshot, parseTokenUsageSnapshot, resolveTokenUsageVisibleContextWindowTokens, tokenUsageHasEstimatedContextWindow, tokenUsageHasEstimatedCurrentTokens };
export type { TokenUsageSnapshot };
