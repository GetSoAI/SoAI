/* SoAI - Chat page configuration change tracking [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/configurationChangeTracking.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getParameterMeta } from '@core/chat/parameters/chatParameterMeta.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { compareParameterValues, isChatConfigurationParameterTabId, type ChatParameters, type ConversationSettingsActionInput } from '@features/chat/public.ts';
import type { ConversationSettingsAction } from '@pages/chat/controllers/chatconfigurationcontroller/types.ts';

export const isConfigurationParameterTab = (tabId: string): boolean => isChatConfigurationParameterTabId(tabId);

export const areParameterValuesEqual = (parameter: string, firstValue: JsonValue | undefined, secondValue: JsonValue | undefined): boolean => {
    const meta = getParameterMeta(parameter);
    const precision = meta && typeof meta.precision === 'number' ? meta.precision : 2;
    return compareParameterValues(firstValue, secondValue, { precision });
};

export const areParameterSetsEqual = (current: ChatParameters | null, baseline: ChatParameters | null): boolean => {
    const currentValues = current ? current : null;
    const baselineValues = baseline ? baseline : null;
    const keys = new Set([...Object.keys(current ? current : {}), ...Object.keys(baseline ? baseline : {})]);
    for (const key of keys) {
        const currentValue = currentValues ? currentValues[key] : undefined;
        const baselineValue = baselineValues ? baselineValues[key] : undefined;
        if (!areParameterValuesEqual(key, currentValue, baselineValue)) {
            return false;
        }
    }
    return true;
};

export const normalizeConversationSettingsAction = (action: ConversationSettingsActionInput | null): ConversationSettingsAction | null => {
    if (!action) {
        return null;
    }
    const handler = typeof action.handler === 'function' ? action.handler : null;
    return { hasChanges: Boolean(action.hasChanges), isValid: action.isValid !== false, handler, isStillValid: action.isStillValid ?? (() => true) };
};
