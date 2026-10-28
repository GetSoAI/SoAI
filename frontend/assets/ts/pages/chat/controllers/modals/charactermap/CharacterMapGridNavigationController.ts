/* SoAI - Character map grid navigation [frontend/assets/ts/pages/chat/controllers/modals/charactermap/CharacterMapGridNavigationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveInlineArrowStep } from '@core/layout/direction.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { CharacterMapQueryResult, CharacterMapResultItem } from '@features/chat/public.ts';
import { resolveCharacterMapCellId, type CharacterMapGridWidget } from '@pages/chat/controllers/modals/charactermap/CharacterMapGridWidget.ts';

interface CharacterMapGridNavigationControllerHost {
    grid: HTMLElement;
    cells: Pick<CharacterMapGridWidget, 'reveal' | 'resolveCell' | 'firstCell' | 'columnCount'>;
    isCurrent(): boolean;
    onActive(item: CharacterMapResultItem | null): void;
    onSelect(): void;
    onError(error: Error): void;
}

class CharacterMapGridNavigationController {
    readonly #host: CharacterMapGridNavigationControllerHost;
    #result: CharacterMapQueryResult = { ids: [], lookup: new Map() };
    #activeId: string | null = null;
    #focusToken = 0;
    #queryGeneration = 0;
    #tabStopId: string | null = null;
    #pendingReveal: AbortController | null = null;

    constructor(host: CharacterMapGridNavigationControllerHost) {
        this.#host = host;
    }

    get activeId(): string | null {
        return this.#activeId;
    }

    commit(result: CharacterMapQueryResult, queryGeneration: number, preferredId: string | null): void {
        this.#focusToken += 1;
        this.#queryGeneration = queryGeneration;
        this.#result = result;
        const activeId = preferredId !== null && result.lookup.has(preferredId) ? preferredId : (result.ids[0] ?? null);
        this.#setActive(activeId, false);
        this.applyRovingTabIndex();
    }

    applyRovingTabIndex(): void {
        const previousCell = this.#tabStopId === null ? null : this.#host.cells.resolveCell(this.#tabStopId);
        previousCell?.classList.remove('is-selected');
        if (previousCell !== null) previousCell.tabIndex = -1;
        const activeCell = this.#activeId === null ? null : this.#host.cells.resolveCell(this.#activeId);
        const entryCell = activeCell ?? this.#host.cells.firstCell();
        if (entryCell !== null) entryCell.tabIndex = 0;
        activeCell?.classList.add('is-selected');
        this.#tabStopId = entryCell === null ? null : resolveCharacterMapCellId(entryCell);
    }

    activateFromElement(element: HTMLElement, focus: boolean): boolean {
        const identifier = resolveCharacterMapCellId(element);
        if (identifier === null || !this.#result.lookup.has(identifier)) return false;
        this.#setActive(identifier, focus);
        return true;
    }

    handleKeydown(event: KeyboardEvent, element: HTMLElement): void {
        const identifier = resolveCharacterMapCellId(element);
        const currentIndex = identifier === null ? -1 : this.#result.ids.indexOf(identifier);
        if (currentIndex < 0) return;
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            this.#host.onSelect();
            return;
        }
        const targetIndex = this.#resolveTargetIndex(event.key, currentIndex);
        if (targetIndex === null) return;
        event.preventDefault();
        const targetId = this.#result.ids[targetIndex];
        if (targetId === undefined) return;
        this.#setActive(targetId, false);
        this.#focusIdentifier(targetId);
    }

    invalidate(): void {
        this.#focusToken += 1;
        this.#abortPendingReveal();
    }

    #setActive(identifier: string | null, focus: boolean): void {
        if (identifier !== null && !this.#result.lookup.has(identifier)) throw new Error('Unknown character-map result identifier');
        this.#focusToken += 1;
        this.#abortPendingReveal();
        this.#activeId = identifier;
        this.applyRovingTabIndex();
        this.#host.onActive(identifier === null ? null : (this.#result.lookup.get(identifier) ?? null));
        if (focus && identifier !== null) this.#focusIdentifier(identifier);
    }

    #focusIdentifier(identifier: string): void {
        this.#abortPendingReveal();
        const mounted = this.#host.cells.resolveCell(identifier);
        if (mounted !== null) {
            mounted.tabIndex = 0;
            mounted.focus();
            return;
        }
        const token = ++this.#focusToken;
        const queryGeneration = this.#queryGeneration;
        const reveal = new AbortController();
        this.#pendingReveal = reveal;
        const ownerDocument = this.#host.grid.ownerDocument;
        const abortOnOutsideFocus = (event: FocusEvent): void => {
            if (event.target instanceof Node && !this.#host.grid.contains(event.target)) reveal.abort();
        };
        ownerDocument.addEventListener('focusin', abortOnOutsideFocus);
        const isCurrentIntent = (): boolean => !reveal.signal.aborted && token === this.#focusToken && queryGeneration === this.#queryGeneration && this.#host.isCurrent();
        const task = this.#host.cells
            .reveal(identifier, { focusOwner: 'caller', signal: reveal.signal })
            .then((revealed) => {
                if (!revealed || !isCurrentIntent()) return;
                this.#releasePendingReveal(reveal);
                this.applyRovingTabIndex();
                this.#host.cells.resolveCell(identifier)?.focus();
            })
            .catch((error: Error) => {
                if (isCurrentIntent()) this.#host.onError(error);
            })
            .finally(() => {
                ownerDocument.removeEventListener('focusin', abortOnOutsideFocus);
                this.#releasePendingReveal(reveal);
            });
        terminateHandledPromise(task);
    }

    #abortPendingReveal(): void {
        const pending = this.#pendingReveal;
        this.#pendingReveal = null;
        pending?.abort();
    }

    #releasePendingReveal(reveal: AbortController): void {
        if (this.#pendingReveal === reveal) this.#pendingReveal = null;
    }

    #resolveTargetIndex(key: string, currentIndex: number): number | null {
        const lastIndex = this.#result.ids.length - 1;
        const inlineStep = resolveInlineArrowStep(key, this.#host.grid);
        if (inlineStep !== 0) return Math.max(0, Math.min(lastIndex, currentIndex + inlineStep));
        if (key === 'ArrowUp') return Math.max(0, currentIndex - this.#host.cells.columnCount());
        if (key === 'ArrowDown') return Math.min(lastIndex, currentIndex + this.#host.cells.columnCount());
        if (key === 'Home') return 0;
        if (key === 'End') return lastIndex;
        if (key === 'PageUp') return Math.max(0, currentIndex - 48);
        if (key === 'PageDown') return Math.min(lastIndex, currentIndex + 48);
        return null;
    }
}

export { CharacterMapGridNavigationController };
