/* SoAI - Logs page controls service [frontend/assets/ts/pages/logs/services/pagecontrols/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolvePageControlSelectValue } from '@core/pagecontrols/selectController.ts';
import { requirePageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import { CORE_LOG_SOURCE } from '@features/logging/public.ts';

const readLogsSourcePreference = (storage: PageControlsStorageInput): string => {
    const state = requirePageControlsStorage(storage).getPageControlState('logs');
    return state.source || CORE_LOG_SOURCE;
};

const resolveLogsSourcePreference = (storage: PageControlsStorageInput, availableSources: readonly string[]): string => {
    const requested = readLogsSourcePreference(storage);
    const resolved = resolvePageControlSelectValue(requested, availableSources, CORE_LOG_SOURCE);
    if (requested !== resolved) persistLogsSourcePreference(storage, resolved);
    return resolved;
};

const persistLogsSourcePreference = (storage: PageControlsStorageInput, source: string): void => {
    requirePageControlsStorage(storage).setPageControlState('logs', {
        source: source || CORE_LOG_SOURCE
    });
};

export { persistLogsSourcePreference, readLogsSourcePreference, resolveLogsSourcePreference };
