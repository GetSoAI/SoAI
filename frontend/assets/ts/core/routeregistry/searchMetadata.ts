/* SoAI - Shared route registry search metadata [frontend/assets/ts/core/routeregistry/searchMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { RouteSearchDefinition } from '@core/routeregistry/contracts.ts';

const SEARCH_PAGE_METADATA: Readonly<Record<string, RouteSearchDefinition>> = Object.freeze({
    dashboard: {
        include: true,
        getTitle: () => i18n.t('search.pages.dashboard.title'),
        getDescription: () => i18n.t('search.pages.dashboard.description')
    },
    chat: {
        include: true,
        getTitle: () => i18n.t('search.pages.chat.title'),
        getDescription: () => i18n.t('search.pages.chat.description')
    },
    plugins: {
        include: true,
        getTitle: () => i18n.t('search.pages.plugins.title'),
        getDescription: () => i18n.t('search.pages.plugins.description')
    },
    models: {
        include: true,
        getTitle: () => i18n.t('search.pages.models.title'),
        getDescription: () => i18n.t('search.pages.models.description')
    },
    hardware: {
        include: true,
        getTitle: () => i18n.t('search.pages.hardware.title'),
        getDescription: () => i18n.t('search.pages.hardware.description')
    },
    metrics: {
        include: true,
        getTitle: () => i18n.t('search.pages.metrics.title'),
        getDescription: () => i18n.t('search.pages.metrics.description')
    },
    power: {
        include: true,
        getTitle: () => i18n.t('search.pages.power.title'),
        getDescription: () => i18n.t('search.pages.power.description')
    },
    settings: {
        include: true,
        getTitle: () => i18n.t('search.pages.settings.title'),
        getDescription: () => i18n.t('search.pages.settings.description')
    },
    fileExplorer: {
        include: true,
        getTitle: () => i18n.t('search.pages.fileExplorer.title'),
        getDescription: () => i18n.t('search.pages.fileExplorer.description')
    },
    updates: {
        include: true,
        getTitle: () => i18n.t('search.pages.updates.title'),
        getDescription: () => i18n.t('search.pages.updates.description')
    },
    help: {
        include: true,
        getTitle: () => i18n.t('search.pages.help.title'),
        getDescription: () => i18n.t('search.pages.help.description')
    },
    about: {
        include: true,
        getTitle: () => i18n.t('search.pages.about.title'),
        getDescription: () => i18n.t('search.pages.about.description')
    }
});

const resolveRouteSearchMetadata = (routeId: string): RouteSearchDefinition => {
    const metadata = SEARCH_PAGE_METADATA[routeId];
    if (!metadata) {
        throw new Error(`Search metadata is not registered for route: ${routeId}`);
    }
    return metadata;
};

export { resolveRouteSearchMetadata };
