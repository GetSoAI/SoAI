/* SoAI - Workspace focus intent, presentation handoff and LRU ownership [frontend/assets/ts/core/pagepanes/focus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { capturePagePaneLayout, playPagePaneLayout, syncPagePaneSplit } from '@core/pagepanes/motion.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { PagePaneSlot } from '@core/pagepanes/contracts.ts';
import { findPagePaneSlot } from '@core/pagepanes/dom.ts';
import { RoutePane } from '@core/routing/router/RoutePane.ts';
import type { PaneCapacity } from '@core/pagepanes/capacity.ts';
import { hasPageContentInputBarrier, setPageContentAvailable, setPageContentReady } from '@core/layout/pageContentInteractivity.ts';
import { runCleanupCallbacks, runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { PAGE_PANE_CLOSE } from '@core/pagepanes/actions.ts';

class PagePaneFocus {
    readonly #intent = new SequenceToken();
    readonly #handoff = new SequenceToken();
    readonly #slots: ReadonlyMap<string, PagePaneSlot>;
    readonly #getContainer: () => HTMLElement | null;
    readonly #onChange: (focusChanged: boolean, userIntent: boolean) => void;
    readonly #onIntent: (intent: number) => void;
    #selected: RoutePane | null = null;
    #ordinal = 0;
    #capacity: PaneCapacity | null = null;

    constructor(slots: ReadonlyMap<string, PagePaneSlot>, getContainer: () => HTMLElement | null, onChange: (focusChanged: boolean, userIntent: boolean) => void, onIntent: (intent: number) => void) {
        this.#slots = slots;
        this.#getContainer = getContainer;
        this.#onChange = onChange;
        this.#onIntent = onIntent;
    }

    get selected(): RoutePane | null {
        return this.#selected;
    }

    claimIntent(): number {
        const intent = this.#intent.next();
        this.#onIntent(intent);
        return intent;
    }

    isCurrentIntent(intent: number): boolean {
        return this.#intent.isActive(intent);
    }

    canSelect(pane: RoutePane): boolean {
        const slot = this.#slots.get(pane.id);
        if (!slot || slot.pane !== pane) throw new Error('Cannot focus a pane outside its workspace');
        return slot.admitted && slot.state === 'mounted' && !hasPageContentInputBarrier(slot.root) && !this.#getContainer()?.hasAttribute('inert');
    }

    select(pane: RoutePane, userIntent: boolean): void {
        const slot = this.#slots.get(pane.id);
        if (!slot || slot.pane !== pane) throw new Error('Cannot focus a pane outside its workspace');
        if (!this.canSelect(pane)) throw createAbortError('Pane is not available for focus');
        const intent = userIntent ? this.claimIntent() : null;
        if (intent !== null && !this.#intent.isActive(intent)) return;
        if (this.#selected === pane) {
            if (userIntent) this.#onChange(false, true);
            return;
        }
        this.#selected = pane;
        slot.focusOrdinal = ++this.#ordinal;
        this.project(this.#capacity, true, userIntent);
    }

    project(capacity: PaneCapacity | null, focusChanged = false, userIntent = false, beforeNotify?: () => void, successor: RoutePane | null = null): void {
        if (capacity !== null) this.#capacity = capacity;
        if (this.#selected && this.#slots.get(this.#selected.id)?.state === 'closing') {
            const ordered = [...this.#slots.values()];
            const selectedIndex = ordered.findIndex((slot) => slot.pane === this.#selected);
            const preferred = successor ? this.#slots.get(successor.id) : null;
            const replacement = preferred?.pane === successor && preferred?.state === 'mounted' ? preferred : [...ordered.slice(0, selectedIndex).reverse(), ...ordered.slice(selectedIndex + 1)].find((slot) => slot.state === 'mounted' || slot.state === 'opening');
            this.#selected = replacement?.pane ?? null;
            if (replacement) replacement.focusOrdinal = ++this.#ordinal;
            focusChanged = true;
        }
        const constrained = this.#capacity !== null && [...this.#slots.values()].filter((slot) => slot.state !== 'parked').length > this.#capacity;
        const handoff = this.#handoff.next();
        const selected = this.#selected;
        const container = this.#getContainer();
        const visibility = [...this.#slots.values()].map((slot) => ({ slot, visible: slot.admitted && slot.state !== 'parked' && slot.state !== 'closing' && (!constrained || slot.pane === selected) }));
        const roots = visibility.map(({ slot }) => slot.root);
        const motion = container && visibility.some(({ slot, visible }) => slot.root.hidden === visible) ? capturePagePaneLayout(container, roots) : null;
        const changes: { pane: RoutePane; visible: boolean; focused: boolean }[] = [];
        const failures: Error[] = [];
        for (const { slot: candidate, visible } of visibility) {
            if (!this.#handoff.isActive(handoff)) break;
            const focused = visible && candidate.pane === selected;
            candidate.root.hidden = !visible;
            setPageContentAvailable(candidate.root, visible);
            setPageContentReady(candidate.root, candidate.state === 'mounted');
            candidate.root.dataset['paneFocused'] = String(focused);
            changes.push({ pane: candidate.pane, visible, focused });
        }
        if (container) container.dataset['paneConstrained'] = String(constrained);
        try {
            if (this.#handoff.isActive(handoff)) RoutePane.setPresentations(changes, beforeNotify);
            else beforeNotify?.();
        } catch (error) {
            failures.push(ensureError(error));
        }
        if (this.#handoff.isActive(handoff)) {
            if (container) syncPagePaneSplit(container, changes.filter((change) => change.visible).length > 1);
            if (motion) playPagePaneLayout(motion, roots);
            this.#onChange(focusChanged, userIntent);
        }
        if (failures.length) throw new AggregateError(failures, 'Pane focus presentation failed');
    }

    invalidate(): void {
        this.#intent.invalidate();
        this.#handoff.invalidate();
    }

    suspend(beforePresentation: readonly (() => void)[]): void {
        this.invalidate();
        const handoff = this.#handoff.value;
        const failures: Error[] = [];
        const container = this.#getContainer();
        if (container) runCleanupStepCollectingFailure(() => setPageContentAvailable(container, false), failures);
        for (const slot of this.#slots.values()) {
            slot.admitted = false;
            runCleanupStepCollectingFailure(() => setPageContentAvailable(slot.root, false), failures);
        }
        const revoke = (): void => runCleanupCallbacks(beforePresentation, (error) => failures.push(error));
        if (this.#handoff.isActive(handoff)) runCleanupStepCollectingFailure(() => this.project(null, false, false, revoke), failures);
        else revoke();
        throwCollectedCleanupFailures(failures);
    }

    reset(): void {
        this.invalidate();
        this.#selected = null;
        this.#ordinal = 0;
        this.#capacity = null;
    }

    handleEvent = (event: Event): void => {
        const container = this.#getContainer();
        if (!(event.target instanceof Element) || container?.hasAttribute('inert')) return;
        if (event.target.closest(`[data-action="${PAGE_PANE_CLOSE}"]`)) return;
        const slot = findPagePaneSlot(event.target, container, this.#slots);
        if (!slot || slot.root.inert || slot.root.hidden || !slot.pane.presentation.isVisible()) return;
        if (event.type === 'focusin' && this.#selected === slot.pane) return;
        this.select(slot.pane, true);
    };
}

export { PagePaneFocus };
