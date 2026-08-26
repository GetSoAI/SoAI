/* SoAI - Settings page search setup [frontend/assets/ts/pages/settings/controllers/settingsSearchSetup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';

export interface SettingsSearchSetupHost extends PageResourcesOwnerHost {
    requireSearchContainer(): HTMLElement;
    isSearchInitialized(container: HTMLElement): boolean;
    createStandardSearch(container: HTMLElement, onSearch: (query: string) => void): { input: HTMLInputElement };
    resolveExistingInput(container: HTMLElement): HTMLInputElement | null;
    setSearchQuery(query: string): void;
    filterSettings(): void;
}

export const setupSettingsSearch = (host: SettingsSearchSetupHost): void => {
    const container = host.requireSearchContainer();
    const initialized = host.isSearchInitialized(container);
    const commitQuery = (raw: string): void => {
        host.setSearchQuery(normalizeSearchMatchQuery(raw));
        host.filterSettings();
    };

    const bindInput = (input: HTMLInputElement): void => {
        host.pageResources.on(input, 'input', (event: Event) => {
            if (!(event.target instanceof HTMLInputElement)) {
                return;
            }
            commitQuery(event.target.value);
        });
    };

    if (!initialized) {
        host.createStandardSearch(container, commitQuery);
        return;
    }

    const existingInput = host.resolveExistingInput(container);
    if (!(existingInput instanceof HTMLInputElement)) {
        throw new Error('Settings search input is missing');
    }
    bindInput(existingInput);
};
