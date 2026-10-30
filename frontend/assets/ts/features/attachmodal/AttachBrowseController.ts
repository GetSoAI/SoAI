/* SoAI - Attachment dialog browser selection, search and preview lifetime [frontend/assets/ts/features/attachmodal/AttachBrowseController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { createAbortSignalScope, isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireSortableColumn, resolveNextSortState } from '@core/ui/tables/sortableTable.ts';
import type { AttachDraftListController } from '@features/attachmodal/AttachDraftListController.ts';
import type { AttachBrowseConsumer } from '@features/attachmodal/browseContracts.ts';
import type { AttachBrowseResult, AttachBrowseSortState } from '@features/attachmodal/browseRecords.ts';
import { ATTACH_BROWSE_SORT_COLUMNS, ATTACH_BROWSE_SORT_DIRECTIONS, sortBrowseResults } from '@features/attachmodal/browseSorting.ts';
import { renderBrowseMessage, setBrowseFooterButtonState } from '@features/attachmodal/browseState.ts';
import { renderBrowseResultsTable } from '@features/attachmodal/browseTable.ts';
import type { AttachBrowseElements } from '@features/attachmodal/contracts.ts';

class AttachBrowseController<TResult extends AttachBrowseResult> {
    readonly #consumer: AttachBrowseConsumer<TResult>;
    readonly #elements: AttachBrowseElements;
    readonly #draftListController: AttachDraftListController;
    readonly #signal: AbortSignal;
    #active = false;
    readonly #searchSequence = new SequenceToken();
    #searchController: AbortController | null = null;
    #results: TResult[] = [];
    #sortState: AttachBrowseSortState = { column: 'name', direction: 'asc' };
    #selectedKey: string | null = null;
    #selectionGeneration = 0;
    #openGeneration = 0;

    constructor(consumer: AttachBrowseConsumer<TResult>, elements: AttachBrowseElements, signal: AbortSignal, drafts: AttachDraftListController) {
        this.#consumer = consumer;
        this.#elements = elements;
        this.#signal = signal;
        this.#draftListController = drafts;
        signal.addEventListener('abort', this.deactivate, { once: true });
        this.#syncFooter();
    }

    activate(): void {
        this.#active = true;
        this.#consumer.activateWorkspace();
        this.#draftListController.activate();
        this.#syncFooter();
        this.#queueSearch('chat:attachModalBrowseSearch');
    }

    readonly deactivate = (): void => {
        this.#active = false;
        this.#searchSequence.invalidate();
        this.#consumer.deactivateWorkspace();
        this.#draftListController.deactivate();
        this.#selectionGeneration += 1;
        this.#abortBrowseActions();
        this.#abortSearch();
        this.#syncFooter();
    };

    async openWorkspacePathPicker(): Promise<void> {
        await this.#consumer.openWorkspacePathPicker();
    }

    handleInput(): void {
        if (!this.#active) {
            return;
        }
        this.#selectionGeneration += 1;
        this.#openGeneration += 1;
        this.#abortBrowseActions();
        this.#selectedKey = null;
        this.#results = [];
        this.#syncFooter();
        this.#queueSearch('chat:attachModalBrowseSearchInput');
    }

    selectResult(resultKey: string | null, actionElement: HTMLElement, event: Event): void {
        if (resultKey === null) {
            return;
        }
        const nextSelectedKey = this.#resolveNextSelectedKey(resultKey, actionElement, event);
        if (this.#selectedKey !== nextSelectedKey) {
            this.#selectionGeneration += 1;
        }
        this.#selectedKey = nextSelectedKey;
        this.#renderResults(false);
        this.#syncFooter();
    }

    async openResult(resultKey: string | null, actionElement: HTMLElement, event: Event): Promise<void> {
        if (resultKey === null) {
            return;
        }
        if (event instanceof MouseEvent && (event.ctrlKey || event.metaKey)) {
            this.selectResult(resultKey, actionElement, event);
            return;
        }
        const result = this.#resultByKey(resultKey);
        if (result === null) {
            return;
        }
        this.#openGeneration += 1;
        const intake = this.#consumer.captureScope();
        this.#abortBrowseActions();
        const openGeneration = this.#openGeneration;
        if (!this.#consumer.hasOwner()) {
            return;
        }
        await this.#consumer.preview(result, () => intake.isCurrent() && this.#isCurrentOpen(openGeneration, result.key));
    }

    sortResults(column: string | null): void {
        if (column === null) {
            return;
        }
        const sortColumn = requireSortableColumn(ATTACH_BROWSE_SORT_COLUMNS, column, 'chat attach browse');
        this.#sortState = resolveNextSortState(this.#sortState, sortColumn, ATTACH_BROWSE_SORT_DIRECTIONS[sortColumn]);
        this.#renderResults(true);
    }

    async previewSelected(): Promise<void> {
        const selected = this.#selectedResult();
        if (selected === null) {
            return;
        }
        const selectionGeneration = this.#selectionGeneration;
        if (!this.#consumer.hasOwner()) {
            return;
        }
        const intake = this.#consumer.captureScope();
        this.#abortBrowseActions();
        await this.#consumer.preview(selected, () => intake.isCurrent() && this.#isCurrentSelection(selectionGeneration, selected.key));
    }

    async attachSelected(): Promise<boolean> {
        const selected = this.#selectedResult();
        if (selected === null) {
            return false;
        }
        const selectionGeneration = this.#selectionGeneration;
        if (!this.#consumer.hasOwner()) {
            return false;
        }
        const intake = this.#consumer.captureScope();
        this.#abortBrowseActions();
        return await this.#consumer.attach(selected, () => intake.isCurrent() && this.#isCurrentSelection(selectionGeneration, selected.key));
    }

    #abortBrowseActions(): void {
        this.#consumer.abortActions();
    }

    #abortSearch(): void {
        const controller = this.#searchController;
        this.#searchController = null;
        if (controller !== null) {
            controller.abort();
        }
    }

    #selectedResult(): TResult | null {
        const key = this.#selectedKey;
        if (key === null) {
            return null;
        }
        return this.#resultByKey(key);
    }

    #resultByKey(key: string): TResult | null {
        return this.#results.find((result) => result.key === key) ?? null;
    }

    #syncFooter(): void {
        const enabled = this.#selectedResult() !== null;
        setBrowseFooterButtonState(this.#elements.previewButton, this.#active, enabled);
        setBrowseFooterButtonState(this.#elements.attachButton, this.#active, enabled);
    }

    #renderResults(animateReorder: boolean): void {
        renderBrowseResultsTable(this.#elements.results, sortBrowseResults(this.#results, this.#sortState), this.#selectedKey, this.#sortState, animateReorder);
    }

    #queueSearch(operation: string): void {
        this.#abortSearch();
        const generation = this.#searchSequence.next();
        const acquisition = this.#consumer.captureSearch();
        this.#consumer.run(operation, () => this.#search(acquisition, generation));
    }

    async #search(acquisition: ReturnType<AttachBrowseConsumer<TResult>['captureSearch']>, generation: number): Promise<void> {
        if (!this.#active || this.#signal.aborted || !this.#searchSequence.isActive(generation)) return;
        const controller = new AbortController();
        const scope = createAbortSignalScope([this.#signal, controller.signal]);
        this.#searchController = controller;
        renderBrowseMessage(this.#elements.results, i18n.t('chat.attachModal.browseLoadingTitle'), i18n.t('chat.attachModal.browseLoadingSubtitle'), true);
        try {
            const query = this.#elements.searchInput.value.trim();
            const outcome = await acquisition.search(query, scope.signal);
            if (!this.#isCurrent(generation, scope.signal) || this.#elements.searchInput.value.trim() !== query) return;
            if (outcome.type === 'superseded') {
                if (outcome.refresh) this.#queueSearch('chat:attachModalBrowseSearchWorkspaceRefresh');
                return;
            }
            if (outcome.type === 'no-owner') {
                if (this.#selectedKey !== null) this.#selectionGeneration += 1;
                this.#results = [];
                this.#selectedKey = null;
                renderBrowseMessage(this.#elements.results, i18n.t('chat.attachModal.browseNeedsConversation'), i18n.t('chat.attachModal.browseEmptySubtitle'));
                this.#syncFooter();
                return;
            }
            this.#results = outcome.results;
            const nextSelectedKey = this.#results.some((result) => result.key === this.#selectedKey) ? this.#selectedKey : null;
            if (nextSelectedKey !== this.#selectedKey) {
                this.#selectionGeneration += 1;
            }
            this.#selectedKey = nextSelectedKey;
            this.#renderResults(false);
            this.#syncFooter();
        } catch (error) {
            if (controller.signal.aborted || isAbortError(error)) {
                return;
            }
            throw ensureError(error);
        } finally {
            if (this.#searchController === controller) {
                this.#searchController = null;
            }
            scope.cleanup();
        }
    }

    #isCurrent(generation: number, signal: AbortSignal): boolean {
        return this.#active && !this.#signal.aborted && !signal.aborted && this.#searchSequence.isActive(generation);
    }

    #isCurrentSelection(selectionGeneration: number, resultKey: string): boolean {
        return this.#active && !this.#signal.aborted && selectionGeneration === this.#selectionGeneration && this.#selectedKey === resultKey;
    }

    #isCurrentOpen(openGeneration: number, resultKey: string): boolean {
        return this.#active && !this.#signal.aborted && openGeneration === this.#openGeneration && this.#resultByKey(resultKey) !== null;
    }

    #resolveNextSelectedKey(resultKey: string, actionElement: HTMLElement, event: Event): string | null {
        const checkboxToggled = actionElement instanceof HTMLInputElement && actionElement.type === 'checkbox';
        const modifierToggled = event instanceof MouseEvent && (event.ctrlKey || event.metaKey);
        if ((checkboxToggled || modifierToggled) && this.#selectedKey === resultKey) {
            return null;
        }
        return resultKey;
    }
}

export { AttachBrowseController };
