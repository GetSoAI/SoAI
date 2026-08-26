/* SoAI - Shared realtime automatic resources state [frontend/assets/ts/core/realtime/streammanager/autoresources/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { AutoResourceState } from '@core/realtime/streammanager/types.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

const MODULE = 'StreamManager';
const AUTO_RESOURCE_EVENT = 'soai:stream:auto-resources';

let autoResourceState: AutoResourceState = Object.freeze({ status: 'idle', error: null, updatedAt: Date.now() });
const autoResourceListeners = new Set<(state: AutoResourceState) => void>();

const setAutoResourceState = (next: Partial<AutoResourceState> | null): AutoResourceState => {
    if (!isObject(next)) {
        return autoResourceState;
    }
    const updated: AutoResourceState = Object.freeze({
        status: next.status ?? autoResourceState.status,
        error: next.error ?? null,
        updatedAt: Date.now()
    });

    if (updated.status === autoResourceState.status && updated.error?.resource === autoResourceState.error?.resource && updated.error?.message === autoResourceState.error?.message) {
        return autoResourceState;
    }

    autoResourceState = updated;
    autoResourceListeners.forEach((listener) => {
        try {
            listener(updated);
        } catch (error) {
            const err = ensureError(error);
            errorHandler.debug(MODULE, 'Auto-resources listener callback failed', err);
        }
    });

    dispatchCustomEvent(AUTO_RESOURCE_EVENT, updated);
    telemetry.emit({
        module: MODULE,
        stage: 'autoResources:state',
        severity: 'info',
        message: 'autoResources:state',
        data: updated
    });

    return updated;
};

const getAutoResourceState = (): AutoResourceState => autoResourceState;

const subscribeAutoResourceState = (listener: (state: AutoResourceState) => void): (() => void) => {
    if (typeof listener !== 'function') {
        return () => {};
    }
    autoResourceListeners.add(listener);
    return () => {
        autoResourceListeners.delete(listener);
    };
};

export { AUTO_RESOURCE_EVENT, getAutoResourceState, setAutoResourceState, subscribeAutoResourceState };
