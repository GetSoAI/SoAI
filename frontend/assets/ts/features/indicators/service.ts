/* SoAI - Indicators feature service [frontend/assets/ts/features/indicators/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { ensureLiveStatusOverlayStorage, readSetting } from '@features/indicators/adapters.ts';
import { activateLiveStatusOverlay, deactivateLiveStatusOverlay } from '@features/indicators/effects.ts';
import { createLiveStatusOverlaySettingChangeHandler, registerSettingListener, unregisterSettingListener } from '@features/indicators/events.ts';
import { LIVE_STATUS_OVERLAY_SERVICE_ID } from '@features/indicators/constants.ts';
import type { SetEnabledOptions } from '@features/indicators/contracts.ts';
import { createLiveStatusOverlayState } from '@features/indicators/state.ts';
import type { LiveStatusOverlayErrorLevel, LiveStatusOverlayErrorReporter, LiveStatusOverlayState, LiveStatusOverlaySettingChangeHandler } from '@features/indicators/types.ts';

const logger = createModuleLogger('LiveStatusOverlay', { defaultLevel: 'debug' });
const createErrorReporter = (): LiveStatusOverlayErrorReporter => {
    return (message: string, error: Error, level: LiveStatusOverlayErrorLevel = 'debug'): void => {
        logger(level, message, error);
    };
};

class LiveStatusOverlay {
    readonly #state: LiveStatusOverlayState;
    readonly #handleError: LiveStatusOverlayErrorReporter;
    readonly #settingChangeHandler: LiveStatusOverlaySettingChangeHandler;
    readonly #timers = new ResourceTracker();

    constructor() {
        this.#state = createLiveStatusOverlayState();
        this.#handleError = createErrorReporter();
        this.#settingChangeHandler = createLiveStatusOverlaySettingChangeHandler((enabled: boolean): Promise<void> => this.applyEnabledState(enabled), this.#handleError);
    }

    async initialize(): Promise<boolean> {
        await ensureLiveStatusOverlayStorage(this.#state, this.#handleError);
        registerSettingListener(this.#state, this.#settingChangeHandler);
        await this.applyEnabledState(readSetting(this.#state, this.#handleError));
        return true;
    }

    async setEnabled(enabled: boolean, options: SetEnabledOptions = {}): Promise<void> {
        const { persist = true } = options;
        await ensureLiveStatusOverlayStorage(this.#state, this.#handleError);
        if (persist && isFunction(this.#state.storage?.setLiveStatusOverlayEnabled)) {
            this.#state.storage.setLiveStatusOverlayEnabled(enabled);
            return;
        }
        await this.applyEnabledState(enabled);
    }

    private async applyEnabledState(enabled: boolean): Promise<void> {
        const nextEnabled = Boolean(enabled);
        if (this.#state.destroyed) {
            if (nextEnabled) {
                throw new Error('Live status overlay has been destroyed');
            }
            return;
        }
        if (nextEnabled && this.#state.enabled && this.#state.active) {
            return;
        }
        if (!nextEnabled && !this.#state.enabled && !this.#state.active) {
            return;
        }
        this.#state.lifecycleGeneration += 1;
        const generation = this.#state.lifecycleGeneration;
        this.#state.enabled = nextEnabled;
        if (nextEnabled) {
            try {
                await this.activate(generation);
            } catch (error) {
                const runtimeError = ensureError(error);
                if (this.#state.lifecycleGeneration === generation) {
                    this.#state.enabled = false;
                    this.deactivate();
                }
                throw runtimeError;
            }
            return;
        }
        this.deactivate();
    }

    private async activate(generation: number): Promise<void> {
        if (this.#state.active) {
            return;
        }
        await activateLiveStatusOverlay(this.#state, this.#handleError, this.#timers, generation);
        if (this.#state.enabled && this.#state.lifecycleGeneration === generation) {
            this.#state.active = true;
        }
    }

    private deactivate(): void {
        try {
            deactivateLiveStatusOverlay(this.#state, this.#timers);
        } catch (error) {
            const runtimeError = ensureError(error);
            this.#handleError('Failed to deactivate live status overlay', runtimeError, 'error');
        } finally {
            this.#timers.cleanup();
            this.#state.enabled = false;
            this.#state.active = false;
        }
    }

    async destroy(...inputArguments: JsonValue[]): Promise<boolean> {
        this.#state.destroyed = true;
        void inputArguments;
        this.deactivate();
        this.#timers.cleanup();
        unregisterSettingListener(this.#state, this.#settingChangeHandler, this.#handleError);
        return true;
    }

    get serviceId(): string {
        return LIVE_STATUS_OVERLAY_SERVICE_ID;
    }
}

export { LiveStatusOverlay };
