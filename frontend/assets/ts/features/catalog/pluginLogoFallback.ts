/* SoAI - Catalog archive logo failure handling [frontend/assets/ts/features/catalog/pluginLogoFallback.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { dom } from '@core/dom/dom.ts';

const substituteFailedPluginLogo = (image: HTMLImageElement): void => {
    if (!image.isConnected || !image.complete || image.naturalWidth > 0) return;
    const fallback = image.dataset['pluginLogoFallback'] ?? '';
    if (!fallback || image.dataset['pluginLogoFallbackApplied'] === 'true' || image.getAttribute('src') === fallback || image.currentSrc === fallback || image.src === fallback) return;
    image.dataset['pluginLogoFallbackApplied'] = 'true';
    image.src = fallback;
};

const bindPluginLogoFallbacks = (root: HTMLElement, signal: AbortSignal): void => {
    const handleError = (event: Event): void => {
        if (event.target instanceof HTMLImageElement) substituteFailedPluginLogo(event.target);
    };
    bindEventGroup([{ target: root, type: 'error', listener: handleError, options: { capture: true } }], signal);
    for (const element of dom.resolveAll('img[data-plugin-logo-fallback]', root)) {
        if (element instanceof HTMLImageElement) substituteFailedPluginLogo(element);
    }
};

const setPluginLogoFallback = (image: HTMLImageElement, fallback: string): void => {
    delete image.dataset['pluginLogoFallbackApplied'];
    if (fallback) image.dataset['pluginLogoFallback'] = fallback;
    else delete image.dataset['pluginLogoFallback'];
};

export { bindPluginLogoFallbacks, setPluginLogoFallback, substituteFailedPluginLogo };
