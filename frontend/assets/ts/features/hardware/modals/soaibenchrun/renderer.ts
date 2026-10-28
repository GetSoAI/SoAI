/* SoAI - SoAI Bench combined run modal renderer [frontend/assets/ts/features/hardware/modals/soaibenchrun/renderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, removeWithPresence } from '@core/animations/presence/public.ts';
import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { dom } from '@core/dom/dom.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { toggleHidden } from '@core/ui/visibility.ts';
import { requireComposerElement, requireModalBody, requireRunList, requireToolbar, resolveComposerFocusTarget } from '@features/hardware/modals/soaibenchrun/dom.ts';
import type { SoAIBenchResultActions } from '@features/hardware/modals/soaibenchrun/resultActions.ts';
import { SoAIBenchRunSectionView } from '@features/hardware/modals/soaibenchrun/sectionRenderer.ts';
import type { SoAIBenchGpuSelection } from '@features/hardware/modals/soaibenchrun/selection.ts';
import type { SoAIBenchRunSessionState } from '@features/hardware/modals/soaibenchrun/sessionState.ts';
import type { SoAIBenchRunModalHost } from '@features/hardware/modals/soaibenchrun/types.ts';

interface SoAIBenchRunModalRendererDependencies {
    host: SoAIBenchRunModalHost;
    modalId: string;
    state: SoAIBenchRunSessionState;
    selection: SoAIBenchGpuSelection;
    resultActions: SoAIBenchResultActions;
    isDeviceBusy(deviceId: string): boolean;
}

class SoAIBenchRunModalRenderer {
    readonly #dependencies: SoAIBenchRunModalRendererDependencies;
    readonly #sections = new Map<string, SoAIBenchRunSectionView>();
    readonly #queue: AnimationFrameRenderQueue<true>;
    #composerMarkup = '';
    #visible = false;
    #scrollTop = 0;

    constructor(dependencies: SoAIBenchRunModalRendererDependencies) {
        this.#dependencies = dependencies;
        this.#queue = new AnimationFrameRenderQueue<true>({
            label: 'Hardware SoAI Bench run modal',
            render: () => this.#render(),
            merge: () => true,
            isDisposed: () => !this.#visible
        });
    }

    show(): void {
        this.#visible = true;
        this.#render();
    }

    hide(): void {
        this.#visible = false;
        this.#queue.cancel();
    }

    schedule(): void {
        if (this.#visible) {
            this.#queue.schedule(true);
        }
    }

    render(): void {
        this.#render();
    }

    #render(): void {
        const modalRoot = this.#modalRoot();
        const hasSections = this.#dependencies.state.entries().length > 0;
        modalRoot.dataset['soaibenchLayout'] = hasSections ? 'runs' : 'composer';
        toggleHidden(requireToolbar(this.#dependencies.host, modalRoot), !hasSections || this.#dependencies.selection.composer.type !== 'closed');
        this.#renderComposer(modalRoot, hasSections);
        this.#syncSections(modalRoot);
    }

    revealSection(sectionId: string): void {
        const view = this.#sections.get(sectionId);
        if (view === undefined) {
            return;
        }
        scrollElementIntoView(view.root, { block: 'start' });
        view.focusHeading();
    }

    revealComposer(): void {
        const composer = requireComposerElement(this.#dependencies.host, this.#modalRoot());
        scrollElementIntoView(composer, { block: 'start' });
        resolveComposerFocusTarget(composer)?.focus({ preventScroll: true });
    }

    focusNewBenchmark(): void {
        const button = dom.resolve('button', requireToolbar(this.#dependencies.host, this.#modalRoot()));
        if (button instanceof HTMLButtonElement) {
            button.focus({ preventScroll: true });
        }
    }

    captureScroll(): void {
        if (this.#visible) {
            this.#scrollTop = requireModalBody(this.#dependencies.host, this.#modalRoot()).scrollTop;
        }
    }

    restoreScroll(): void {
        requireModalBody(this.#dependencies.host, this.#modalRoot()).scrollTop = this.#scrollTop;
    }

    resolveActionButton(runId: string, action: string): HTMLButtonElement | null {
        const entry = this.#dependencies.state.entries().find((candidate) => candidate.runId === runId);
        const view = entry === undefined ? undefined : this.#sections.get(entry.sectionId);
        const button = view === undefined ? null : dom.resolve(`[data-action="${action}"]`, view.root);
        return button instanceof HTMLButtonElement ? button : null;
    }

    reset(): void {
        this.hide();
        for (const view of this.#sections.values()) {
            view.destroy();
            removeWithPresence(view.root);
        }
        this.#sections.clear();
        this.#scrollTop = 0;
    }

    #renderComposer(modalRoot: HTMLElement, hasSections: boolean): void {
        const composer = requireComposerElement(this.#dependencies.host, modalRoot);
        const selection = this.#dependencies.selection;
        toggleHidden(composer, selection.composer.type === 'closed');
        const markup = selection.render({ modalId: this.#dependencies.modalId, hasSections, isBusy: (deviceId) => this.#dependencies.isDeviceBusy(deviceId), hasHistory: (deviceId) => this.#dependencies.state.hasHistory(deviceId) });
        if (markup.html === this.#composerMarkup) {
            return;
        }
        const hadFocus = composer.contains(composer.ownerDocument.activeElement);
        this.#composerMarkup = markup.html;
        this.#dependencies.host.setHTML(composer, markup);
        if (hadFocus) {
            resolveComposerFocusTarget(composer)?.focus({ preventScroll: true });
        }
    }

    #syncSections(modalRoot: HTMLElement): void {
        const list = requireRunList(this.#dependencies.host, modalRoot);
        const entries = this.#dependencies.state.entries();
        const current = new Set(entries.map((entry) => entry.sectionId));
        for (const [sectionId, view] of this.#sections) {
            if (!current.has(sectionId)) {
                view.destroy();
                this.#sections.delete(sectionId);
                removeWithPresence(view.root);
            }
        }
        for (const entry of entries) {
            const context = { historyAvailable: this.#dependencies.state.hasHistory(entry.request.deviceId), publishing: this.#dependencies.resultActions.isPublishing(entry.runId), freshness: this.#dependencies.state.freshness };
            const existing = this.#sections.get(entry.sectionId);
            if (existing !== undefined) {
                existing.render(entry, context);
                continue;
            }
            const view = new SoAIBenchRunSectionView(this.#dependencies.host, entry);
            view.render(entry, context);
            this.#sections.set(entry.sectionId, view);
            insertWithPresence(list, view.root, null);
        }
    }

    #modalRoot(): HTMLElement {
        return this.#dependencies.host.modals.requireElement(this.#dependencies.modalId);
    }
}

export { SoAIBenchRunModalRenderer };
