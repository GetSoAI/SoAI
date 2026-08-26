/* SoAI - Shared UI primitives collection [frontend/assets/ts/core/uiprimitives/viewmode/collection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { ViewModeController } from '@core/uiprimitives/viewmode/controller.ts';
import { resolveInitialViewMode } from '@core/uiprimitives/viewmode/storage.ts';
import type { ViewMode } from '@core/uiprimitives/viewmode/types.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type CollectionDisplayMode = Extract<ViewMode, 'cards' | 'list'>;

interface CollectionDisplayModeHost extends PageServicesOwnerHost {
    viewMode: CollectionDisplayMode;
    viewModeController: ViewModeController | null;
}

interface CollectionDisplayModeUi {
    root: HTMLElement;
    grid: HTMLElement;
    listBody: HTMLElement;
    viewModeToggleButton: HTMLButtonElement;
}

interface CollectionDisplayModeOverrideHost extends PageDomOwnerHost {
    viewMode: CollectionDisplayMode;
}

interface CollectionDisplayModeOverrideOptions {
    gridSelector: string;
    listSelector: string;
    itemDataKey: string;
}

interface CollectionDisplayModeOverrides {
    resolveContainer: () => HTMLElement | null;
    resolveItemIdentifier: (element: HTMLElement) => string | null;
}

interface CollectionDisplayModeControllerOptions {
    storageKey: string;
    context: string;
    prepareCollectionViewModeChange?: (() => void) | undefined;
    reapplyCollection(): void;
    queueResponsiveLayoutUpdate?: (() => void) | undefined;
}

interface CollectionDisplayModeListControllerOptions extends CollectionDisplayModeControllerOptions {
    syncSortIndicators?: ((table: HTMLTableElement) => void) | undefined;
}

interface CollectionDisplayModeElementRenderOptions<TItem> {
    viewMode: CollectionDisplayMode;
    item: TItem;
    context: string;
    renderCard: (item: TItem) => Element | null;
    renderListRow: (item: TItem) => HTMLElement | null;
}

const COLLECTION_DISPLAY_MODES: readonly [CollectionDisplayMode, CollectionDisplayMode] = ['cards', 'list'];
const COLLECTION_DISPLAY_MODE_ICONS: Record<ViewMode, IconName> = { cards: 'dashboard', list: 'view-list', icons: 'dashboard' };

const resolveInitialCollectionDisplayMode = (storageKey: string): CollectionDisplayMode => {
    const mode = resolveInitialViewMode({
        storageKey,
        allowedModes: COLLECTION_DISPLAY_MODES,
        fallback: 'cards'
    });
    if (mode === 'cards' || mode === 'list') {
        return mode;
    }
    throw new Error('Resolved collection display mode is invalid');
};

const createCollectionDisplayModeOverrides = (host: CollectionDisplayModeOverrideHost, options: CollectionDisplayModeOverrideOptions): CollectionDisplayModeOverrides => ({
    resolveContainer: (): HTMLElement | null => (host.viewMode === 'list' ? host.pageDom.optionalHTMLElement(options.listSelector) : host.pageDom.optionalHTMLElement(options.gridSelector)),
    resolveItemIdentifier: (element): string | null => element.getAttribute(`data-${options.itemDataKey}`)
});

const getCollectionDisplayModeLabels = (): Record<ViewMode, string> => ({
    cards: i18n.t('common.actions.cardView'),
    list: i18n.t('common.actions.listView'),
    icons: i18n.t('common.actions.cardView')
});

const initializeCollectionDisplayModeController = (host: CollectionDisplayModeHost, ui: CollectionDisplayModeUi, options: CollectionDisplayModeControllerOptions): void => {
    host.viewModeController = new ViewModeController({
        root: ui.root,
        button: ui.viewModeToggleButton,
        modes: COLLECTION_DISPLAY_MODES,
        activeMode: host.viewMode,
        storageKey: options.storageKey,
        labels: getCollectionDisplayModeLabels(),
        icons: COLLECTION_DISPLAY_MODE_ICONS,
        getIconSync: (iconName, iconOptions) => host.services.getIconSync(iconName, iconOptions),
        onModeChanging: () => options.prepareCollectionViewModeChange?.(),
        onModeChanged: (mode) => {
            if (mode !== 'cards' && mode !== 'list') {
                throw new Error(`${options.context} received an unsupported collection view mode`);
            }
            host.viewMode = mode;
            options.reapplyCollection();
            options.queueResponsiveLayoutUpdate?.();
        }
    });
};

const requireCollectionDisplayModeTable = (listBody: HTMLElement, context: string): HTMLTableElement => {
    const table = listBody.closest('table');
    if (!(table instanceof HTMLTableElement)) {
        throw new Error(`${context} list body is missing table ancestor`);
    }
    return table;
};

const initializeCollectionDisplayModeControllerWithList = (host: CollectionDisplayModeHost, ui: CollectionDisplayModeUi, options: CollectionDisplayModeListControllerOptions): void => {
    initializeCollectionDisplayModeController(host, ui, options);
    if (options.syncSortIndicators) {
        options.syncSortIndicators(requireCollectionDisplayModeTable(ui.listBody, options.context));
    }
};

const renderCollectionDisplayModeElement = <TItem>(options: CollectionDisplayModeElementRenderOptions<TItem>): Element => {
    const element = options.viewMode === 'list' ? options.renderListRow(options.item) : options.renderCard(options.item);
    if (!element) {
        throw new Error(`${options.context} renderer returned no element`);
    }
    return element;
};

const toggleCollectionDisplayMode = (host: CollectionDisplayModeHost, context: string): void => {
    if (!host.viewModeController) {
        throw new Error(`${context} view mode controller is unavailable`);
    }
    host.viewModeController.toggle();
};

export { COLLECTION_DISPLAY_MODE_ICONS, COLLECTION_DISPLAY_MODES, createCollectionDisplayModeOverrides, getCollectionDisplayModeLabels, initializeCollectionDisplayModeController, initializeCollectionDisplayModeControllerWithList, renderCollectionDisplayModeElement, requireCollectionDisplayModeTable, resolveInitialCollectionDisplayMode, toggleCollectionDisplayMode };
export type { CollectionDisplayMode, CollectionDisplayModeControllerOptions, CollectionDisplayModeElementRenderOptions, CollectionDisplayModeHost, CollectionDisplayModeListControllerOptions, CollectionDisplayModeOverrideHost, CollectionDisplayModeOverrideOptions, CollectionDisplayModeOverrides, CollectionDisplayModeUi };
