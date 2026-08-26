/* SoAI - Plugins page runtime support [frontend/assets/ts/pages/plugins/controllers/pluginsPageRuntimeSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { pluginsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';

interface SanitizerAdapter {
    escapeHtml: (value: JsonValue) => string;
    escapeAttribute: (value: JsonValue) => string;
    sanitizeUrl: (value: JsonValue, options?: Record<string, JsonValue>) => string | null;
}

interface ExecuteItemDeletionOptions {
    identifier: string;
    confirmTitle: string;
    confirmMessage: string;
    confirmButton: string;
    getStream: () => Promise<StreamActionHandle>;
    gridSelector: string;
    findCard: (grid: HTMLElement | null, id: string) => HTMLElement | null;
    pendingClass: string;
    successMessage: string;
    onAccepted?: (taskId: string) => void;
    projectLocally?: boolean;
}

const PLUGINS_GRID = pluginsPageConfig.grid;
const PLUGIN_CARD_SELECTOR = PLUGINS_GRID.cardSelector;
const PLUGIN_EMPTY_STATES = PLUGINS_GRID.emptyStateIds;

export { PLUGIN_CARD_SELECTOR, PLUGIN_EMPTY_STATES, PLUGINS_GRID };

export type { ExecuteItemDeletionOptions, SanitizerAdapter };
