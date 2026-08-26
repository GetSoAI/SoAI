/* SoAI - Prompts page view mode controller [frontend/assets/ts/pages/prompts/controllers/page/viewModeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionConfigurationOptions } from '@core/routing/pages/pagetypes/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { createCollectionDisplayModeOverrides, initializeCollectionDisplayModeControllerWithList, toggleCollectionDisplayMode, type CollectionDisplayModeHost } from '@core/uiprimitives/viewmode/public.ts';
import type { PromptsRuntimeContext } from '@pages/prompts/controllers/page/contracts.ts';
import { applyPromptsListSortIndicators } from '@pages/prompts/controllers/page/listSortingController.ts';
import type { PromptsUiRefs } from '@pages/prompts/types.ts';

const PROMPTS_VIEW_MODE_STORAGE_KEY = 'soai.prompts.viewMode';

type PromptsViewModeHost = PromptsRuntimeContext;

const getDisplayModeHost = (host: PromptsViewModeHost): CollectionDisplayModeHost => ({
    services: host.owners.services,
    get viewMode() {
        return host.state.viewMode;
    },
    set viewMode(value) {
        host.state.viewMode = value;
    },
    get viewModeController() {
        return host.state.viewModeController;
    },
    set viewModeController(value) {
        host.state.viewModeController = value;
    }
});

const initializePromptsViewMode = (host: PromptsViewModeHost, ui: PromptsUiRefs): void => {
    initializeCollectionDisplayModeControllerWithList(getDisplayModeHost(host), ui, {
        storageKey: PROMPTS_VIEW_MODE_STORAGE_KEY,
        context: 'Prompts',
        prepareCollectionViewModeChange: () => {
            const collection = host.owners.collections.runtime;
            if (!collection) throw new Error('Prompts collection is unavailable for view mode preparation');
            collection.prepareForViewModeChange();
        },
        reapplyCollection: () => {
            const collection = host.owners.collections.runtime;
            if (!collection) throw new Error('Prompts collection is unavailable for view mode rebuild');
            collection.rebuildForViewMode();
        },
        syncSortIndicators: (table) => applyPromptsListSortIndicators(host, table)
    });
};

const togglePromptsViewMode = (host: PromptsViewModeHost): void => {
    toggleCollectionDisplayMode(getDisplayModeHost(host), 'Prompts');
};

const createPromptsCollectionViewOverrides = (host: PromptsViewModeHost): Partial<CollectionConfigurationOptions> => ({
    ...createCollectionDisplayModeOverrides(
        {
            pageDom: host.owners.pageDom,
            get viewMode() {
                return host.state.viewMode;
            }
        },
        {
            gridSelector: '#prompts-grid',
            listSelector: '#prompts-list-body',
            itemDataKey: 'prompt-id'
        }
    ),
    loadingLabel: () => i18n.t('prompts.loading.morePrompts')
});

export { createPromptsCollectionViewOverrides, initializePromptsViewMode, togglePromptsViewMode };
export type { PromptsViewModeHost };
