/* SoAI - Shared storage sync service [frontend/assets/ts/core/storage/service/events/sync/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createStorageSyncAdapterHandlers } from '@core/storage/service/events/sync/adapters.ts';
import { applyLocalStorageState, bootstrapStorageSync, createThemeApplier } from '@core/storage/service/events/sync/effects.ts';
import type { StorageSyncDependencies, StorageSyncHandlers } from '@core/storage/service/events/sync/types.ts';

const createStorageSyncHandlers = ({ state, dependencies, createDefaults, adapters, effects, syncLocal, ensureMainState, flushPending }: StorageSyncDependencies): StorageSyncHandlers => {
    const adapterHandlers = createStorageSyncAdapterHandlers({
        state,
        dependencies,
        createDefaults,
        adapters,
        effects,
        syncLocal,
        ensureMainState
    });

    const applyTheme = createThemeApplier({ state, syncLocal, scheduleBroadcast: adapterHandlers.scheduleBroadcast });

    const applyLocal = (): void => {
        applyLocalStorageState({
            state,
            adapters,
            effects,
            syncLocal,
            ensureMainState,
            applyTheme
        });
    };

    const ready = bootstrapStorageSync({
        state,
        adapters,
        effects,
        flushPending,
        applyTheme,
        ensureMainState,
        syncLocal,
        scheduleBroadcast: adapterHandlers.scheduleBroadcast,
        connectShared: () => adapterHandlers.connectShared(applyTheme),
        broadcast: adapterHandlers.broadcast,
        applyLocal
    });

    return {
        scheduleBroadcast: adapterHandlers.scheduleBroadcast,
        applyTheme,
        ready
    };
};

export { createStorageSyncHandlers };
