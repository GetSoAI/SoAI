/* SoAI - Character map modal session controller [frontend/assets/ts/pages/chat/controllers/modals/charactermap/ChatCharacterMapModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveDelegatedActionElement } from '@core/dom/dataAction.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createBusyDisabledToken, setBusyDisabledState, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { copyTextWithHostClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { CHARACTER_MAP_ACTIONS, CharacterMapCatalogIndex, isCharacterMapAction, type CharacterMapAction, type CharacterMapQueryResult, type CharacterMapResultItem } from '@features/chat/public.ts';
import { CharacterMapGridNavigationController } from '@pages/chat/controllers/modals/charactermap/CharacterMapGridNavigationController.ts';
import { CharacterMapGridWidget } from '@pages/chat/controllers/modals/charactermap/CharacterMapGridWidget.ts';
import { CharacterMapViewStateController } from '@pages/chat/controllers/modals/charactermap/CharacterMapViewStateController.ts';
import { resolveCharacterMapModalRefs } from '@pages/chat/controllers/modals/charactermap/dom.ts';
import type { CharacterMapModalHost, CharacterMapModalRefs } from '@pages/chat/controllers/modals/charactermap/types.ts';
import { populateCharacterMapSelectors, projectCharacterMapActive, projectCharacterMapResult, projectStagingActions, resetCharacterMapView, showCharacterMapLoadFailure, showCharacterMapLoading, showCharacterMapReady, showCharacterMapResultFailure } from '@pages/chat/controllers/modals/charactermap/view.ts';

const SEARCH_DELAY_MS = 80;

class ChatCharacterMapModalController implements EventListenerObject {
    readonly #host: CharacterMapModalHost;
    readonly #signal: AbortSignal;
    readonly #refs: CharacterMapModalRefs;
    readonly #timers = new ResourceTracker();
    readonly #renderer: CharacterMapGridWidget;
    readonly #navigation: CharacterMapGridNavigationController;
    readonly #viewState: CharacterMapViewStateController;
    #catalogIndex: CharacterMapCatalogIndex | null = null;
    #committedResult: CharacterMapQueryResult = { ids: [], lookup: new Map() };
    #candidate: { generation: number; result: CharacterMapQueryResult; preferredId: string | null; type: 'query' | 'rollback' } | null = null;
    #queryGeneration = 0;
    #queryTimer: number | null = null;
    #loadAttempt = 0;
    #copyToken: BusyDisabledToken | null = null;
    #composing = false;
    #resultsUnavailable = false;
    #disposed = false;

    constructor(host: CharacterMapModalHost, modal: HTMLElement, signal: AbortSignal) {
        this.#host = host;
        this.#signal = signal;
        this.#refs = resolveCharacterMapModalRefs(modal);
        resetCharacterMapView(this.#refs);
        this.#renderer = new CharacterMapGridWidget({
            grid: this.#refs.grid,
            empty: this.#refs.empty,
            loadingLabel: () => i18n.t('common.loading'),
            onCommit: () => this.#handleRendererCommit(),
            onError: (error) => this.#handleRendererError(error)
        });
        this.#navigation = new CharacterMapGridNavigationController({
            grid: this.#refs.grid,
            reveal: (identifier) => this.#renderer.reveal(identifier),
            resolveCell: (identifier) => this.#renderer.resolveCell(identifier),
            isCurrent: () => this.#isCurrent(),
            onActive: (item) => this.#projectActive(item),
            onSelect: () => this.#selectActive(),
            onError: (error) => this.#handleQueryError(error)
        });
        this.#viewState = new CharacterMapViewStateController({
            refs: this.#refs,
            renderer: this.#renderer,
            initialState: host.initialViewState,
            save: (state) => host.saveViewState(state),
            onError: (error) => host.feedback.handle(error, 'Character-map view state persistence failed', { notify: false }),
            onSubsetChange: () => this.#executeImmediateQuery(),
            signal
        });
        this.#bind();
        this.#startLoad();
    }

    handleEvent(event: Event): void {
        if (!this.#isCurrent()) return;
        if (event.type === 'click') this.#handleClick(event);
        if (event.type === 'dblclick') this.#handleDoubleClick(event);
        if (event.type === 'keydown') this.#handleKeydown(event);
        if (event.type === 'input') this.#handleInput(event);
        if (event.type === 'compositionstart') this.#beginComposition();
        if (event.type === 'compositionend') {
            this.#composing = false;
            this.#scheduleQuery();
        }
        if (event.type === 'focusin') this.#handleFocus(event);
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#queryGeneration += 1;
        this.#navigation.invalidate();
        this.#timers.clearAllTimers();
        if (this.#copyToken !== null) {
            setBusyDisabledState(this.#refs.copy, { isBusy: false, token: this.#copyToken });
            this.#copyToken = null;
        }
        this.#viewState.dispose();
        this.#renderer.dispose();
    }

    #bind(): void {
        const listener = (event: Event): void => this.handleEvent(event);
        bindEventGroup(
            [
                { target: this.#refs.modal, type: 'click', listener },
                { target: this.#refs.grid, type: 'dblclick', listener },
                { target: this.#refs.grid, type: 'keydown', listener },
                { target: this.#refs.grid, type: 'focusin', listener },
                { target: this.#refs.search, type: 'input', listener },
                { target: this.#refs.search, type: 'keydown', listener },
                { target: this.#refs.search, type: 'compositionstart', listener },
                { target: this.#refs.search, type: 'compositionend', listener },
                { target: this.#refs.staging, type: 'input', listener }
            ],
            this.#signal
        );
    }

    #startLoad(): void {
        const attempt = ++this.#loadAttempt;
        showCharacterMapLoading(this.#refs);
        this.#host.runTask(`chat:characterMap:load:${attempt}`, async () => {
            try {
                const catalog = await this.#host.loadCatalog();
                if (!this.#isCurrent() || attempt !== this.#loadAttempt) return;
                const catalogIndex = new CharacterMapCatalogIndex(catalog);
                populateCharacterMapSelectors(this.#refs, catalogIndex);
                this.#viewState.restoreSubset(catalogIndex);
                this.#catalogIndex = catalogIndex;
                showCharacterMapReady(this.#refs);
                this.#executeImmediateQuery();
            } catch (error) {
                if (!this.#isCurrent() || isAbortError(error)) return;
                this.#host.feedback.handle(ensureError(error), 'Character-map catalog load failed', { notify: false });
                showCharacterMapLoadFailure(this.#refs);
            }
        });
    }

    #scheduleQuery(): void {
        if (this.#composing || this.#catalogIndex === null) return;
        if (this.#queryTimer !== null) this.#timers.clearTimeout(this.#queryTimer);
        const generation = ++this.#queryGeneration;
        this.#navigation.invalidate();
        this.#rollbackCandidate(generation);
        this.#queryTimer = this.#timers.setTimeout(() => {
            this.#queryTimer = null;
            if (generation === this.#queryGeneration) this.#executeQuery(generation);
        }, SEARCH_DELAY_MS);
    }

    #executeImmediateQuery(): void {
        if (this.#queryTimer !== null) this.#timers.clearTimeout(this.#queryTimer);
        this.#queryTimer = null;
        this.#navigation.invalidate();
        this.#executeQuery(++this.#queryGeneration);
    }

    #executeQuery(generation: number): void {
        if (this.#catalogIndex === null || !this.#isCurrent()) return;
        try {
            const selectorId = this.#refs.subset.value;
            if (!this.#catalogIndex.isSelectorId(selectorId)) throw new Error('Unknown character-map selector');
            const result = this.#catalogIndex.query(selectorId, this.#refs.search.value);
            this.#candidate = { generation, result, preferredId: this.#navigation.activeId, type: 'query' };
            this.#refs.grid.setAttribute('aria-busy', 'true');
            setControlDisabledState(this.#refs.select, true);
            this.#renderer.update(result, true, this.#viewState.resolveRestoreAnchor(selectorId));
        } catch (error) {
            this.#rollbackCandidate(generation);
            this.#handleQueryError(ensureError(error));
        }
    }

    #handleRendererCommit(): void {
        const candidate = this.#candidate;
        if (candidate !== null && candidate.generation === this.#queryGeneration) {
            this.#candidate = null;
            this.#committedResult = candidate.result;
            this.#navigation.commit(candidate.result, candidate.generation, candidate.preferredId);
            this.#viewState.commit(this.#refs.subset.value);
            this.#refs.grid.setAttribute('aria-busy', 'false');
            if (candidate.type === 'query') this.#resultsUnavailable = false;
            projectCharacterMapResult(this.#refs, candidate.result.ids.length, this.#activeItem());
            if (this.#resultsUnavailable) showCharacterMapResultFailure(this.#refs);
            return;
        }
        this.#navigation.applyRovingTabIndex();
    }

    #handleRendererError(error: Error): void {
        this.#candidate = null;
        this.#refs.grid.setAttribute('aria-busy', 'false');
        this.#handleQueryError(error);
    }

    #handleQueryError(error: Error): void {
        if (!this.#isCurrent()) return;
        this.#resultsUnavailable = true;
        this.#host.feedback.handle(ensureError(error), 'Character-map result rendering failed', { notify: false });
        projectCharacterMapResult(this.#refs, this.#committedResult.ids.length, this.#activeItem());
        showCharacterMapResultFailure(this.#refs);
    }

    #handleClick(event: Event): void {
        const actionElement = resolveDelegatedActionElement({ event, root: this.#refs.modal, ignoreDisabled: true, preventDefault: 'never' });
        if (actionElement === null) return;
        const action = actionElement.dataset.action;
        if (!isCharacterMapAction(action)) {
            if (action.startsWith('character-map:')) throw new Error(`Unknown character-map action ${action}`);
            return;
        }
        event.stopPropagation();
        this.#dispatchAction(action, actionElement);
    }

    #dispatchAction(action: CharacterMapAction, element: HTMLElement): void {
        if (action === CHARACTER_MAP_ACTIONS.ACTIVATE_RESULT && this.#candidate === null) this.#navigation.activateFromElement(element, false);
        if (action === CHARACTER_MAP_ACTIONS.SEARCH) this.#executeImmediateQuery();
        if (action === CHARACTER_MAP_ACTIONS.RETRY) this.#startLoad();
        if (action === CHARACTER_MAP_ACTIONS.SELECT) this.#selectActive();
        if (action === CHARACTER_MAP_ACTIONS.COPY) this.#copy();
        if (action === CHARACTER_MAP_ACTIONS.INSERT) this.#insert();
    }

    #handleDoubleClick(event: Event): void {
        if (this.#candidate !== null) return;
        const target = event.target;
        if (!(target instanceof HTMLElement) || !this.#navigation.activateFromElement(target, false)) return;
        event.preventDefault();
        this.#selectActive();
    }

    #handleKeydown(event: Event): void {
        if (!(event instanceof KeyboardEvent)) return;
        if (event.currentTarget === this.#refs.search && event.key === 'Enter' && !this.#composing) {
            event.preventDefault();
            this.#executeImmediateQuery();
            return;
        }
        const target = event.target;
        if (this.#candidate !== null) return;
        if (target instanceof HTMLElement) this.#navigation.handleKeydown(event, target);
    }

    #handleInput(event: Event): void {
        if (event.currentTarget === this.#refs.search) this.#scheduleQuery();
        if (event.currentTarget === this.#refs.staging) projectStagingActions(this.#refs, this.#copyToken !== null);
    }

    #handleFocus(event: Event): void {
        if (this.#candidate !== null) return;
        const target = event.target;
        if (target instanceof HTMLElement) this.#navigation.activateFromElement(target, false);
    }

    #selectActive(): void {
        const item = this.#activeItem();
        if (item === null) return;
        this.#refs.staging.value += item.text;
        const caret = this.#refs.staging.value.length;
        this.#refs.staging.setSelectionRange(caret, caret);
        projectStagingActions(this.#refs, this.#copyToken !== null);
    }

    #copy(): void {
        if (this.#copyToken !== null || this.#refs.staging.value.length === 0) return;
        const token = setBusyDisabledState(this.#refs.copy, { isBusy: true, createToken: createBusyDisabledToken });
        this.#copyToken = token;
        const text = this.#refs.staging.value;
        this.#host.runTask(`chat:characterMap:copy:${this.#loadAttempt}:${token}`, async () => {
            try {
                await copyTextWithHostClipboardFeedback({ hasClipboardSupport: () => this.#host.hasClipboardSupport(), copyToClipboard: (value, options) => this.#host.copyToClipboard(value, options), showNotification: (message, type, duration) => this.#host.feedback.show(message, type, duration) }, { text, preserveText: true, successMessage: i18n.t('common.clipboard.copied'), errorMessage: i18n.t('common.clipboard.copyFailed'), unavailableMessage: i18n.t('common.clipboard.copyUnavailable') });
            } catch (error) {
                if (this.#isCurrent()) {
                    this.#host.feedback.handle(ensureError(error), 'Character-map clipboard copy failed', { notify: false });
                    this.#host.feedback.show(i18n.t('common.clipboard.copyFailed'), 'error');
                }
            } finally {
                if (!this.#isCurrent() || this.#copyToken !== token) return;
                setBusyDisabledState(this.#refs.copy, { isBusy: false, token });
                this.#copyToken = null;
                projectStagingActions(this.#refs, false);
            }
        });
    }

    #insert(): void {
        const text = this.#refs.staging.value;
        if (text.length === 0) return;
        try {
            this.#host.insertText(text);
            this.#host.closeAfterInsert();
        } catch (error) {
            this.#host.feedback.handle(ensureError(error), 'Character-map insertion failed', { notify: false });
            this.#host.feedback.show(i18n.t('chat.characterMap.insertFailure'), 'error');
        }
    }

    #projectActive(item: CharacterMapResultItem | null): void {
        projectCharacterMapActive(this.#refs, item);
    }

    #beginComposition(): void {
        this.#composing = true;
        if (this.#queryTimer !== null) this.#timers.clearTimeout(this.#queryTimer);
        this.#queryTimer = null;
        this.#navigation.invalidate();
        this.#rollbackCandidate(++this.#queryGeneration);
    }

    #rollbackCandidate(generation: number): void {
        if (this.#candidate === null) return;
        this.#candidate = { generation, result: this.#committedResult, preferredId: this.#navigation.activeId, type: 'rollback' };
        this.#renderer.update(this.#committedResult, false);
    }

    #activeItem(): CharacterMapResultItem | null {
        const activeId = this.#navigation.activeId;
        return activeId === null ? null : (this.#committedResult.lookup.get(activeId) ?? null);
    }

    #isCurrent(): boolean {
        return !this.#disposed && !this.#signal.aborted;
    }
}

export { ChatCharacterMapModalController };
