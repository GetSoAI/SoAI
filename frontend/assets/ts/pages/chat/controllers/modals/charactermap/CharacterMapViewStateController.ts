/* SoAI - Character map view-state lifecycle [frontend/assets/ts/pages/chat/controllers/modals/charactermap/CharacterMapViewStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { CHARACTER_MAP_DEFAULT_FONT_ID, CHARACTER_MAP_FONT_CLASSES, getCharacterMapFont, isCharacterMapFontId, type CharacterMapCatalogIndex, type CharacterMapFontId } from '@features/chat/public.ts';
import type { CharacterMapGridWidget } from '@pages/chat/controllers/modals/charactermap/CharacterMapGridWidget.ts';
import type { CharacterMapViewState } from '@pages/chat/controllers/modals/charactermap/state.ts';
import type { CharacterMapModalRefs } from '@pages/chat/controllers/modals/charactermap/types.ts';

const SCROLL_PERSIST_DELAY_MS = 120;

interface CharacterMapViewStateControllerHost {
    refs: CharacterMapModalRefs;
    renderer: CharacterMapGridWidget;
    initialState: CharacterMapViewState | null;
    save(state: CharacterMapViewState): void;
    onError(error: Error): void;
    onSubsetChange(): void;
    signal: AbortSignal;
}

class CharacterMapViewStateController {
    readonly #host: CharacterMapViewStateControllerHost;
    readonly #timers = new ResourceTracker();
    #fontId: CharacterMapFontId;
    #selectorId: string;
    #latestAnchor: CollectionViewportAnchor | null;
    #restoreAnchor: CollectionViewportAnchor | null;
    #scrollTimer: number | null = null;
    #captureEnabled = false;
    #persistenceFailed = false;

    constructor(host: CharacterMapViewStateControllerHost) {
        this.#host = host;
        this.#fontId = host.initialState?.fontId ?? CHARACTER_MAP_DEFAULT_FONT_ID;
        this.#selectorId = host.initialState?.selectorId ?? '';
        this.#latestAnchor = host.initialState?.anchor ?? null;
        this.#restoreAnchor = host.initialState?.anchor ?? null;
        this.#applyFont();
        this.#bind();
    }

    restoreSubset(index: CharacterMapCatalogIndex): string {
        if (!index.isSelectorId(this.#selectorId)) {
            this.#selectorId = index.defaultSelectorId;
            this.#latestAnchor = null;
            this.#restoreAnchor = null;
        }
        this.#host.refs.subset.value = this.#selectorId;
        return this.#selectorId;
    }

    #selectSubset(selectorId: string): void {
        if (selectorId === this.#selectorId) return;
        this.#selectorId = selectorId;
        this.#latestAnchor = null;
        this.#restoreAnchor = null;
        this.#captureEnabled = false;
        this.#persist();
    }

    #selectFont(fontId: string): void {
        if (!isCharacterMapFontId(fontId)) throw new Error('Unknown character-map font');
        this.#fontId = fontId;
        this.#applyFont();
        this.#persist();
    }

    resolveRestoreAnchor(selectorId: string): CollectionViewportAnchor | null {
        return selectorId === this.#selectorId ? this.#restoreAnchor : null;
    }

    commit(selectorId: string): void {
        this.#selectorId = selectorId;
        this.#restoreAnchor = null;
        this.#captureEnabled = true;
        this.#captureAnchor();
        this.#persist();
    }

    #handleScroll(): void {
        if (!this.#captureEnabled || this.#persistenceFailed) return;
        this.#captureAnchor();
        if (this.#scrollTimer !== null) this.#timers.clearTimeout(this.#scrollTimer);
        this.#scrollTimer = this.#timers.setTimeout(() => {
            this.#scrollTimer = null;
            this.#persist();
        }, SCROLL_PERSIST_DELAY_MS);
    }

    dispose(): void {
        if (this.#scrollTimer !== null) this.#timers.clearTimeout(this.#scrollTimer);
        this.#scrollTimer = null;
        this.#timers.clearAllTimers();
        this.#persist();
    }

    #applyFont(): void {
        this.#host.refs.grid.classList.remove(...CHARACTER_MAP_FONT_CLASSES);
        this.#host.refs.grid.classList.add(getCharacterMapFont(this.#fontId).className);
        this.#host.refs.font.value = this.#fontId;
    }

    #bind(): void {
        const listener = (event: Event): void => {
            if (event.type === 'scroll') {
                this.#handleScroll();
                return;
            }
            if (event.currentTarget === this.#host.refs.font) this.#selectFont(this.#host.refs.font.value);
            if (event.currentTarget === this.#host.refs.subset) {
                this.#selectSubset(this.#host.refs.subset.value);
                this.#host.onSubsetChange();
            }
        };
        bindEventGroup(
            [
                { target: this.#host.refs.grid, type: 'scroll', listener, options: { passive: true } },
                { target: this.#host.refs.font, type: 'change', listener },
                { target: this.#host.refs.subset, type: 'change', listener }
            ],
            this.#host.signal
        );
    }

    #captureAnchor(): void {
        this.#latestAnchor = this.#host.renderer.captureViewportAnchor();
    }

    #persist(): void {
        if (this.#persistenceFailed || this.#selectorId.length === 0) return;
        try {
            this.#host.save({ fontId: this.#fontId, selectorId: this.#selectorId, anchor: this.#latestAnchor });
        } catch (error) {
            this.#persistenceFailed = true;
            this.#host.onError(ensureError(error));
        }
    }
}

export { CharacterMapViewStateController };
