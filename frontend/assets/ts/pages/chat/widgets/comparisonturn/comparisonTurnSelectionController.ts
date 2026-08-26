/* SoAI - Comparison-turn selection state (active variant index + manual overrides) [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnSelectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { ActiveComparisonRun, ConversationProjectionAnalysis } from '@features/chat/public.ts';

type ComparisonNavDirection = 'prev' | 'next';

class ComparisonTurnSelectionController {
    readonly #activeVariantIndexByAssistantTurnTimestamp = new Map<number, number>();
    readonly #manualSelectionTurns = new Set<number>();

    syncSelectionFromAnalysis(analysis: ConversationProjectionAnalysis): void {
        const statesByTurn = analysis.comparisonStatesByTurn;
        const streamingMeta = analysis.streamingAssistantMeta;
        const seen = new Set<number>();

        for (const [assistantTurnTimestamp, state] of statesByTurn.entries()) {
            seen.add(assistantTurnTimestamp);
            const variantCount = ComparisonTurnSelectionController.#resolveEffectiveVariantCount({
                assistantTurnTimestamp,
                activeComparisonRun: analysis.activeComparisonRun,
                comparisonVariantTotal: state.comparisonVariantTotal,
                invalidReason: state.invalidReason
            });
            const maxIndex = Math.max(0, variantCount - 1);

            const streamingVariantIndex = streamingMeta && streamingMeta.assistantTurnTimestamp === assistantTurnTimestamp ? streamingMeta.modelVariantIndex : null;
            let nextActive = this.#resolveActiveVariantIndex(assistantTurnTimestamp, maxIndex);

            if (streamingVariantIndex !== null) {
                if (this.#manualSelectionTurns.has(assistantTurnTimestamp)) {
                    const bounded = clampNumber(nextActive, 0, maxIndex);
                    if (bounded === clampNumber(streamingVariantIndex, 0, maxIndex)) {
                        this.#manualSelectionTurns.delete(assistantTurnTimestamp);
                        nextActive = bounded;
                    } else {
                        nextActive = bounded;
                    }
                } else {
                    nextActive = clampNumber(streamingVariantIndex, 0, maxIndex);
                }
            } else {
                const hasManualSelection = this.#manualSelectionTurns.has(assistantTurnTimestamp);
                if (hasManualSelection && nextActive > maxIndex) {
                    this.#manualSelectionTurns.delete(assistantTurnTimestamp);
                }
                if (!this.#manualSelectionTurns.has(assistantTurnTimestamp)) {
                    nextActive = clampNumber(nextActive, 0, maxIndex);
                }
            }

            this.#activeVariantIndexByAssistantTurnTimestamp.set(assistantTurnTimestamp, nextActive);
        }

        this.#pruneState(seen);
    }

    resolveActiveVariantIndexByAssistantTurnTimestamp(): ReadonlyMap<number, number> {
        return new Map(this.#activeVariantIndexByAssistantTurnTimestamp);
    }

    resolveActiveVariantIndexForAssistantTurnTimestamp(assistantTurnTimestamp: number): number {
        return this.#activeVariantIndexByAssistantTurnTimestamp.get(assistantTurnTimestamp) ?? 0;
    }

    resolveActiveVariantIndexForVariantCount(assistantTurnTimestamp: number, variantCount: number): number {
        const maxIndex = Math.max(0, variantCount - 1);
        return clampNumber(this.#resolveActiveVariantIndex(assistantTurnTimestamp, maxIndex), 0, maxIndex);
    }

    navigate(inputArguments: { assistantTurnTimestamp: number; direction: ComparisonNavDirection; variantCount: number }): { assistantTurnTimestamp: number; direction: ComparisonNavDirection } | null {
        const maxIndex = Math.max(0, inputArguments.variantCount - 1);
        if (maxIndex <= 0) {
            return null;
        }
        const current = this.#resolveActiveVariantIndex(inputArguments.assistantTurnTimestamp, maxIndex);
        const nextIndex = inputArguments.direction === 'prev' ? current - 1 : current + 1;
        const nextActive = clampNumber(nextIndex, 0, maxIndex);
        this.#activeVariantIndexByAssistantTurnTimestamp.set(inputArguments.assistantTurnTimestamp, nextActive);
        this.#manualSelectionTurns.add(inputArguments.assistantTurnTimestamp);
        return { assistantTurnTimestamp: inputArguments.assistantTurnTimestamp, direction: inputArguments.direction };
    }

    setManualSelection(inputArguments: { assistantTurnTimestamp: number; variantCount: number; nextActiveVariantIndex: number }): void {
        const maxIndex = Math.max(0, inputArguments.variantCount - 1);
        if (maxIndex <= 0) {
            return;
        }
        const nextActive = clampNumber(inputArguments.nextActiveVariantIndex, 0, maxIndex);
        this.#activeVariantIndexByAssistantTurnTimestamp.set(inputArguments.assistantTurnTimestamp, nextActive);
        this.#manualSelectionTurns.add(inputArguments.assistantTurnTimestamp);
    }

    #resolveActiveVariantIndex(assistantTurnTimestamp: number, maxIndex: number): number {
        const stored = this.#activeVariantIndexByAssistantTurnTimestamp.get(assistantTurnTimestamp) ?? 0;
        if (!Number.isInteger(stored) || stored < 0) {
            return 0;
        }
        return stored > maxIndex ? maxIndex : stored;
    }

    static #resolveEffectiveVariantCount(inputArguments: { assistantTurnTimestamp: number; activeComparisonRun: ActiveComparisonRun | null; comparisonVariantTotal: number; invalidReason: string | null }): number {
        if (inputArguments.invalidReason !== null) {
            return 1;
        }
        if (inputArguments.activeComparisonRun && inputArguments.activeComparisonRun.assistantTurnTimestamp === inputArguments.assistantTurnTimestamp) {
            return Math.max(inputArguments.comparisonVariantTotal, Math.max(1, inputArguments.activeComparisonRun.variantCount));
        }
        return Math.max(1, inputArguments.comparisonVariantTotal);
    }

    #pruneState(seen: ReadonlySet<number>): void {
        for (const key of this.#activeVariantIndexByAssistantTurnTimestamp.keys()) {
            if (!seen.has(key)) {
                this.#activeVariantIndexByAssistantTurnTimestamp.delete(key);
            }
        }
        for (const key of this.#manualSelectionTurns.values()) {
            if (!seen.has(key)) {
                this.#manualSelectionTurns.delete(key);
            }
        }
    }
}

export { ComparisonTurnSelectionController };
export type { ComparisonNavDirection };
