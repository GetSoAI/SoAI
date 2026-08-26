/* SoAI - Frontend application initialize core services [frontend/assets/ts/app/bootstrap/stages/initializeCoreServices.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCoreTimeout } from '@core/runtime/runtimeContext.ts';
import { getConnectionState } from '@core/connectionstate/service.ts';
import { getBranding } from '@core/branding/public.ts';
import { getStateManager } from '@core/state/public.ts';
import { requireOperationErrorNotifier } from '@core/operationErrorNotifierRuntime.ts';
import { requireSoaiOsCapabilities } from '@core/soaiOsCapabilitiesRuntime.ts';
import { isSoaiOsCapabilitiesService } from '@core/soaiOsAccess.ts';
import { isStorageServiceContract } from '@core/storage/guards.ts';
import { requireStorageService } from '@core/storage/runtime.ts';
import { getTooltipService } from '@core/ui/tooltips/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';

const requireStorageServiceContract = (): StorageService => {
    const candidate = requireStorageService();
    if (!isStorageServiceContract(candidate)) {
        throw new Error('core.storage must expose ready: Promise<void>');
    }
    return candidate;
};

let initializationPromise: Promise<void> | null = null;

const initializeCoreServices = async (): Promise<void> => {
    if (!initializationPromise) {
        initializationPromise = (async (): Promise<void> => {
            const storageService = requireStorageServiceContract();
            const timeoutMs = getCoreTimeout('CORE_MODULES');
            await withTimeout(storageService.ready, { timeoutMs: timeoutMs, timeoutMessage: `core.storage ready timed out after ${timeoutMs}ms` });

            await getStateManager().initialize();

            const connectionState = getConnectionState();
            if (isObject(connectionState) && isFunction(connectionState['initialize'])) {
                await connectionState['initialize']();
            }

            const soaiOsCapabilities = requireSoaiOsCapabilities();
            if (!isSoaiOsCapabilitiesService(soaiOsCapabilities)) {
                throw new Error('core.soaiOsCapabilities must expose the required service contract');
            }
            await soaiOsCapabilities.ensureReady();

            await getBranding().initialize();
            getTooltipService().initialize();
            requireOperationErrorNotifier().initialize();
        })();
    }
    try {
        await initializationPromise;
    } catch (error) {
        initializationPromise = null;
        throw error;
    }
};

const resetInitializeCoreServices = (): void => {
    initializationPromise = null;
};

export { initializeCoreServices, resetInitializeCoreServices };
