/* SoAI - Comparison-turn navigation state + focus sync [frontend/assets/ts/pages/chat/widgets/comparisonturn/ChatComparisonTurnNavigationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { hasDataActionElement } from '@core/dom/dataAction.ts';
import { CHAT_ACTIONS, type ActiveComparisonRun, type ConversationProjectionAnalysis } from '@features/chat/public.ts';
import { parseNonNegativeIntegerAttribute } from '@pages/chat/widgets/comparisonturn/comparisonTurnDomParsingController.ts';
import { CHAT_COMPARISON_MESSAGE_SELECTOR, CHAT_COMPARISON_TURN_SELECTOR, CHEVRON_NEXT_SELECTOR, CHEVRON_PREV_SELECTOR } from '@pages/chat/widgets/comparisonturn/comparisonTurnDomSelectorsController.ts';
import { ComparisonTurnCarouselController } from '@pages/chat/widgets/comparisonturn/comparisonTurnCarouselController.ts';
import { ComparisonTurnSelectionController, type ComparisonNavDirection } from '@pages/chat/widgets/comparisonturn/comparisonTurnSelectionController.ts';

export class ChatComparisonTurnNavigationController {
    #pendingFocus: { assistantTurnTimestamp: number; direction: ComparisonNavDirection } | null = null;
    readonly #selection = new ComparisonTurnSelectionController();
    readonly #carousel: ComparisonTurnCarouselController;

    constructor(timers: { setTimer: (functionValue: () => void, delayMs: number) => number; clearTimer: (timerId: number) => void }) {
        this.#carousel = new ComparisonTurnCarouselController(timers);
    }

    dispose(): void {
        this.#carousel.dispose();
    }

    sync(container: Element): void {
        const pending = this.#pendingFocus;
        if (!pending) {
            return;
        }
        this.#pendingFocus = null;

        const activeVariantIndex = this.#selection.resolveActiveVariantIndexForAssistantTurnTimestamp(pending.assistantTurnTimestamp);
        const preferredRootSelector = `${CHAT_COMPARISON_MESSAGE_SELECTOR}[data-assistant-turn-ts="${CSS.escape(String(pending.assistantTurnTimestamp))}"][data-model-variant-index="${CSS.escape(String(activeVariantIndex))}"]`;
        const alternateRootSelector = `${CHAT_COMPARISON_MESSAGE_SELECTOR}[data-assistant-turn-ts="${CSS.escape(String(pending.assistantTurnTimestamp))}"]`;
        const rootSelector = dom.resolve(preferredRootSelector, container) ? preferredRootSelector : alternateRootSelector;
        const root = dom.resolve(rootSelector, container);
        if (!(root instanceof HTMLElement)) {
            return;
        }

        const preferredSelector = pending.direction === 'prev' ? CHEVRON_PREV_SELECTOR : CHEVRON_NEXT_SELECTOR;
        const preferred = dom.resolve(preferredSelector, root);
        if (preferred instanceof HTMLButtonElement && !preferred.hidden && !preferred.disabled) {
            preferred.focus({ preventScroll: true });
            return;
        }

        const alternateSelector = pending.direction === 'prev' ? CHEVRON_NEXT_SELECTOR : CHEVRON_PREV_SELECTOR;
        const alternate = dom.resolve(alternateSelector, root);
        if (alternate instanceof HTMLButtonElement && !alternate.hidden && !alternate.disabled) {
            alternate.focus({ preventScroll: true });
            return;
        }

        const timestampButton = dom.resolve('button.message-timestamp-btn', root);
        if (timestampButton instanceof HTMLButtonElement) {
            timestampButton.focus({ preventScroll: true });
        }
    }

    syncSelectionFromAnalysis(analysis: ConversationProjectionAnalysis): void {
        this.#selection.syncSelectionFromAnalysis(analysis);
    }

    resolveActiveVariantIndexByAssistantTurnTimestamp(): ReadonlyMap<number, number> {
        return this.#selection.resolveActiveVariantIndexByAssistantTurnTimestamp();
    }

    syncCarousels(container: Element, inputArguments: { isCurrentStreaming: boolean; activeComparisonRun: ActiveComparisonRun | null }): void {
        this.#carousel.syncCarousels(container, inputArguments, this.#selection);
    }

    navigate(inputArguments: { assistantTurnTimestamp: number; direction: ComparisonNavDirection; variantCount: number }): void {
        const pending = this.#selection.navigate(inputArguments);
        if (!pending) {
            return;
        }
        this.#pendingFocus = pending;
    }

    showVariant(analysis: ConversationProjectionAnalysis, assistantTurnTimestamp: number, variantIndex: number): boolean {
        this.#pendingFocus = null;
        const state = analysis.comparisonStatesByTurn.get(assistantTurnTimestamp);
        const variants = analysis.assistantMessagesByTurnAndVariant.get(assistantTurnTimestamp);
        if (!Number.isSafeInteger(variantIndex) || variantIndex < 0 || !state || state.invalidReason !== null || variantIndex >= state.comparisonVariantTotal || !variants?.has(variantIndex)) return false;
        this.#selection.setManualSelection({ assistantTurnTimestamp, variantCount: state.comparisonVariantTotal, nextActiveVariantIndex: variantIndex });
        return true;
    }

    async waitForVariantSettled(container: Element, assistantTurnTimestamp: number, variantIndex: number, signal: AbortSignal, timeoutMs: number): Promise<boolean> {
        const root = dom.resolve(`${CHAT_COMPARISON_TURN_SELECTOR}[data-assistant-turn-ts="${CSS.escape(String(assistantTurnTimestamp))}"]`, container);
        if (!(root instanceof HTMLElement)) return !signal.aborted && variantIndex === 0;
        return await this.#carousel.waitForVariantSettled(root, variantIndex, signal, timeoutMs);
    }

    resolveAssistantTurnTimestampFromActionElement(actionElement: HTMLElement): number | null {
        return parseNonNegativeIntegerAttribute(actionElement.getAttribute('data-assistant-turn-ts'), 'data-assistant-turn-ts');
    }

    resolveVariantCountFromActionElement(actionElement: HTMLElement): number | null {
        return parseNonNegativeIntegerAttribute(actionElement.getAttribute('data-comparison-variant-total'), 'data-comparison-variant-total');
    }

    resolveDirectionFromActionElement(actionElement: HTMLElement): ComparisonNavDirection | null {
        if (!hasDataActionElement(actionElement)) {
            return null;
        }
        const action = actionElement.dataset.action;
        if (action === CHAT_ACTIONS.COMPARISON_PREV) {
            return 'prev';
        }
        if (action === CHAT_ACTIONS.COMPARISON_NEXT) {
            return 'next';
        }
        return null;
    }
}
