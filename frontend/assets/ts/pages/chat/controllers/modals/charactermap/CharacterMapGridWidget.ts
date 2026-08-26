/* SoAI - Character map bounded grid rendering [frontend/assets/ts/pages/chat/controllers/modals/charactermap/CharacterMapGridWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BoundedCollectionRenderer } from '@core/data/boundedcollectionrenderer/service.ts';
import type { BoundedCollectionCommitContext, CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { CHARACTER_MAP_ACTIONS, type CharacterMapQueryResult, type CharacterMapResultItem } from '@features/chat/public.ts';

const CHARACTER_MAP_ITEM_ATTRIBUTE = 'data-character-map-id';

interface CharacterMapGridWidgetHost {
    grid: HTMLElement;
    empty: HTMLElement;
    loadingLabel(): string;
    onCommit(context: BoundedCollectionCommitContext): void;
    onError(error: Error): void;
}

const resolveCharacterMapCellId = (element: HTMLElement): string | null => element.getAttribute(CHARACTER_MAP_ITEM_ATTRIBUTE);

class CharacterMapGridWidget {
    readonly #renderer: BoundedCollectionRenderer<CharacterMapResultItem>;
    readonly #cells = new Map<string, HTMLButtonElement>();

    constructor(host: CharacterMapGridWidgetHost) {
        this.#renderer = new BoundedCollectionRenderer({
            resolveContainer: () => host.grid,
            resolveEmptyState: () => host.empty,
            loadingLabel: host.loadingLabel,
            renderAllItems: true,
            resolveItemIdentifier: resolveCharacterMapCellId,
            renderItem: (item, context) => {
                const button = host.grid.ownerDocument.createElement('button');
                button.type = 'button';
                button.className = 'search-item chat-character-map-cell';
                button.setAttribute(CHARACTER_MAP_ITEM_ATTRIBUTE, context.id);
                button.dataset['action'] = CHARACTER_MAP_ACTIONS.ACTIVATE_RESULT;
                button.tabIndex = -1;
                button.textContent = item.text;
                const label = `${item.text} · ${item.codePointText} · ${item.name}`;
                button.setAttribute('aria-label', label);
                setTooltipText(button, `${item.codePointText} · ${item.name}`);
                return button;
            },
            onCommit: (context) => {
                this.#cells.clear();
                for (const element of context.mountedElements) {
                    const identifier = resolveCharacterMapCellId(element);
                    if (element instanceof HTMLButtonElement && identifier !== null) this.#cells.set(identifier, element);
                }
                host.onCommit(context);
            },
            onError: host.onError
        });
    }

    update(result: CharacterMapQueryResult, resetScroll = true, restoreViewportAnchor: CollectionViewportAnchor | null = null): void {
        if (restoreViewportAnchor === null) {
            this.#renderer.update({ ids: result.ids, lookup: result.lookup, resetScroll });
            return;
        }
        this.#renderer.update({ ids: result.ids, lookup: result.lookup, resetScroll, restoreViewportAnchor });
    }

    reveal(identifier: string): Promise<boolean> {
        return this.#renderer.reveal(identifier);
    }

    resolveCell(identifier: string): HTMLButtonElement | null {
        return this.#cells.get(identifier) ?? null;
    }

    captureViewportAnchor(): CollectionViewportAnchor | null {
        return this.#renderer.captureViewportAnchor();
    }

    dispose(): void {
        this.#cells.clear();
        this.#renderer.dispose();
    }
}

export { CHARACTER_MAP_ITEM_ATTRIBUTE, CharacterMapGridWidget, resolveCharacterMapCellId };
