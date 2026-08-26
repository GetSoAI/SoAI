/* SoAI - Indicators feature adapters [frontend/assets/ts/features/indicators/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { getStreamResources } from '@core/realtime/streammanager/public.ts';
import { isFunction, isThenable } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import { LIVE_STATUS_OVERLAY_STORAGE_READY_TIMEOUT_MS } from '@features/indicators/constants.ts';
import { isStorageInterface, isTelemetryService } from '@features/indicators/guards.ts';
import type { StorageInterface, StreamManagerInterface, LiveStatusOverlayErrorReporter, LiveStatusOverlayState, TelemetryServiceInterface } from '@features/indicators/types.ts';

const ensureLiveStatusOverlayStorage = async (state: LiveStatusOverlayState, reportError: LiveStatusOverlayErrorReporter): Promise<StorageInterface> => {
    if (state.storage) {
        return state.storage;
    }

    const storageService = resolveKernelService('core.storage');
    if (!isStorageInterface(storageService)) {
        throw new Error('LiveStatusOverlay requires core.storage');
    }

    const readyValue = storageService.ready;
    if (isThenable(readyValue)) {
        try {
            await Promise.race([
                readyValue,
                sleepMs(LIVE_STATUS_OVERLAY_STORAGE_READY_TIMEOUT_MS).then((): never => {
                    throw new Error('Storage ready timeout');
                })
            ]);
        } catch (error) {
            const runtimeError = ensureError(error);
            reportError('Storage readiness failed or timed out', ensureError(runtimeError), 'error');
        }
    }

    state.storage = storageService;
    return storageService;
};

const getTelemetryServiceFromState = (state: LiveStatusOverlayState): TelemetryServiceInterface => {
    if (!state.telemetry && isTelemetryService(telemetry)) {
        state.telemetry = telemetry;
    }

    if (!state.telemetry) {
        throw new Error('Telemetry service unavailable');
    }

    return state.telemetry;
};

const resolveStreamManager = async (state: LiveStatusOverlayState): Promise<StreamManagerInterface> => {
    if (state.streamManager && isFunction(state.streamManager.getDiagnostics)) {
        return state.streamManager;
    }

    const manager = getStreamResources();
    if (!isFunction(manager.getDiagnostics)) {
        throw new Error('Stream manager must expose getDiagnostics');
    }

    state.streamManager = manager;
    return manager;
};

const readBooleanSetting = (getter: (() => boolean) | undefined, message: string, reportError: LiveStatusOverlayErrorReporter): boolean => {
    if (!isFunction(getter)) {
        return false;
    }
    try {
        return Boolean(getter());
    } catch (error) {
        const runtimeError = ensureError(error);
        reportError(message, runtimeError, 'error');
        throw runtimeError;
    }
};

const writeBooleanSetting = (setter: ((value: boolean) => void) | undefined, value: boolean, message: string, reportError: LiveStatusOverlayErrorReporter): void => {
    if (!isFunction(setter)) {
        return;
    }

    try {
        setter(value);
    } catch (error) {
        const runtimeError = ensureError(error);
        reportError(message, runtimeError, 'error');
    }
};

const readSetting = (state: LiveStatusOverlayState, reportError: LiveStatusOverlayErrorReporter): boolean => {
    return readBooleanSetting(state.storage?.getLiveStatusOverlayEnabled, 'Failed to read live status overlay enabled setting', reportError);
};

const writeSetting = (state: LiveStatusOverlayState, enabled: boolean, reportError: LiveStatusOverlayErrorReporter): void => {
    writeBooleanSetting(state.storage?.setLiveStatusOverlayEnabled, enabled, 'Failed to persist live status overlay preference', reportError);
};

export { ensureLiveStatusOverlayStorage, getTelemetryServiceFromState, readSetting, resolveStreamManager, writeSetting };
