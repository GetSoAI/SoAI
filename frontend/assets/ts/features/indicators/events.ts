/* SoAI - Indicators feature events [frontend/assets/ts/features/indicators/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { getEventHub } from '@core/environment/public.ts';
import { isBoolean, isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LIVE_STATUS_OVERLAY_SETTING_CHANGED_EVENT } from '@features/indicators/constants.ts';
import type { LiveStatusOverlayErrorReporter, LiveStatusOverlayState, LiveStatusOverlaySettingChangeHandler } from '@features/indicators/types.ts';

const createLiveStatusOverlaySettingChangeHandler = (applyEnabledState: (enabled: boolean) => Promise<void>, reportError: LiveStatusOverlayErrorReporter): LiveStatusOverlaySettingChangeHandler => {
    const handleEvent = async (event: Event): Promise<void> => {
        if (!event) {
            return;
        }

        if (!(typeof CustomEvent === 'function' && event instanceof CustomEvent)) {
            return;
        }

        const detailValue = event.detail;
        if (!isObject(detailValue)) {
            return;
        }

        const enabledValue = detailValue['enabled'];
        if (!isBoolean(enabledValue)) {
            return;
        }
        const enabled = enabledValue;

        try {
            await applyEnabledState(enabled);
        } catch (error) {
            const runtimeError = ensureError(error);
            reportError('Failed to apply live status overlay preference', runtimeError);
        }
    };

    return (event: Event): void => {
        terminateHandledPromise(handleEvent(event));
    };
};

const registerSettingListener = (state: LiveStatusOverlayState, handler: (event: Event) => void): void => {
    if (state.settingListenerRegistered) {
        return;
    }

    const eventHub = getEventHub();
    eventHub.addEventListener(LIVE_STATUS_OVERLAY_SETTING_CHANGED_EVENT, handler);
    state.settingListenerRegistered = true;
};

const unregisterSettingListener = (state: LiveStatusOverlayState, handler: (event: Event) => void, reportError: LiveStatusOverlayErrorReporter): void => {
    if (!state.settingListenerRegistered) {
        return;
    }

    const eventHub = getEventHub();
    try {
        eventHub.removeEventListener(LIVE_STATUS_OVERLAY_SETTING_CHANGED_EVENT, handler);
    } catch (error) {
        const runtimeError = ensureError(error);
        reportError('Failed to remove setting listener', runtimeError);
    }

    state.settingListenerRegistered = false;
};

export { createLiveStatusOverlaySettingChangeHandler, registerSettingListener, unregisterSettingListener };
