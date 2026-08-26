/* SoAI - Shared background tasks adapters [frontend/assets/ts/core/backgroundtasks/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import type { AuthInstance, StorageInstance } from '@core/backgroundtasks/types.ts';
import { isAuthInstance, isStorageInstance } from '@core/backgroundtasks/guards.ts';

const resolveStorage = (): StorageInstance => {
    const instance = requireStorageService();
    if (!isStorageInstance(instance)) {
        throw new Error('BackgroundTasks requires core.storage.getSolidBackground() and core.storage.getWallpaperOverlay()');
    }
    return instance;
};

const resolveAuthManager = (): AuthInstance => {
    const manager = getAuthManager();
    if (!isAuthInstance(manager)) {
        throw new Error('BackgroundTasks requires core.auth.isAuthenticated');
    }
    return manager;
};

export { resolveAuthManager, resolveStorage };
