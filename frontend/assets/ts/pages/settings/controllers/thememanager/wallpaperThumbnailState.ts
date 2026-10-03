/* SoAI - Built-in wallpaper thumbnail loading state [frontend/assets/ts/pages/settings/controllers/thememanager/wallpaperThumbnailState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalClosestElement } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import type { AddThemeManagerCleanup } from '@pages/settings/controllers/thememanager/contracts.ts';

const finishWallpaperThumbnailLoading = (option: Element): void => {
    setAriaBusy(option, false);
    option.removeAttribute('data-busy-spinner');
};

const setupWallpaperThumbnailLoading = (options: HTMLElement, pageResources: PageResources, addCleanup: AddThemeManagerCleanup): void => {
    const finishThumbnailLoading = (event: Event): void => {
        if (!(event.target instanceof HTMLImageElement)) {
            return;
        }
        const option = optionalClosestElement(event.target, '.wallpaper-builtin-option', options);
        if (option !== null) {
            finishWallpaperThumbnailLoading(option);
        }
    };

    addCleanup(pageResources.on(options, 'load', finishThumbnailLoading, { capture: true }));
    addCleanup(pageResources.on(options, 'error', finishThumbnailLoading, { capture: true }));
    for (const candidate of dom.resolveAll('img', options)) {
        if (!(candidate instanceof HTMLImageElement) || !candidate.complete) {
            continue;
        }
        const option = optionalClosestElement(candidate, '.wallpaper-builtin-option', options);
        if (option !== null) {
            finishWallpaperThumbnailLoading(option);
        }
    }
};

export { setupWallpaperThumbnailLoading };
