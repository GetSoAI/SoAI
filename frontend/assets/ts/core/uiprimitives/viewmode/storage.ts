/* SoAI - Shared UI primitives storage [frontend/assets/ts/core/uiprimitives/viewmode/storage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { readStorageJson, removeStorageKey, writeStorageJson } from '@core/storage/ttlStorageCache.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ViewMode, ViewModeValidator } from '@core/uiprimitives/viewmode/types.ts';

const createViewModeValidator = (allowedModes: readonly ViewMode[]): ViewModeValidator => {
    return (value: JsonValue | null | undefined): value is ViewMode => {
        for (const mode of allowedModes) {
            if (value === mode) {
                return true;
            }
        }
        return false;
    };
};

const readStoredViewMode = (storageKey: string, validate: ViewModeValidator): ViewMode | null => {
    let stored: JsonValue | null | undefined | null;
    try {
        stored = readStorageJson('localStorage', storageKey);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('ViewModeStorage', 'Removed invalid stored view mode preference', { storageKey, message: runtimeError.message });
        removeStorageKey('localStorage', storageKey);
        return null;
    }
    return validate(stored) ? stored : null;
};

const persistViewMode = (storageKey: string, mode: ViewMode): void => {
    writeStorageJson('localStorage', storageKey, mode);
};

const resolveInitialViewMode = (options: { storageKey: string; allowedModes: readonly ViewMode[]; fallback: ViewMode }): ViewMode => {
    const validate = createViewModeValidator(options.allowedModes);
    const stored = readStoredViewMode(options.storageKey, validate);
    if (stored) {
        return stored;
    }
    if (!validate(options.fallback)) {
        throw new Error(`View mode fallback "${options.fallback}" is not allowed`);
    }
    return options.fallback;
};

export { createViewModeValidator, persistViewMode, readStoredViewMode, resolveInitialViewMode };
