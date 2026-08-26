/* SoAI - Shared plugins system requirements [frontend/assets/ts/core/plugins/systemRequirements.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isNullOrUndefined, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';

interface PluginSystemRequirements {
    messages?: JsonValue[] | null;
    blockingActions?: JsonValue[] | null;
}

interface PluginSystemRequirementsCarrier {
    systemRequirements?: PluginSystemRequirements | JsonValue | null;
}

const isPluginSystemRequirementsCarrier = <T>(plugin: T): plugin is T & PluginSystemRequirementsCarrier => typeof plugin === 'object' && plugin !== null;

const normalizeRequirementStringList = (entries: readonly JsonValue[], label: string): string[] => {
    return entries.map((entry, index) => {
        if (!isString(entry)) {
            throw new TypeError(`${label} entry ${index} must be a string`);
        }
        return entry.trim();
    });
};

const getPluginSystemRequirementMessages = <T>(plugin: T, action: string): string[] => {
    if (!isPluginSystemRequirementsCarrier(plugin)) {
        throw new TypeError('Plugin system requirements require a plugin object');
    }
    const systemRequirements = plugin.systemRequirements;
    if (isNullOrUndefined(systemRequirements)) {
        return [];
    }
    if (!isJsonObject(systemRequirements)) {
        throw new TypeError('Plugin system_requirements must be an object');
    }
    const messages = systemRequirements['messages'];
    if (isNullOrUndefined(messages)) {
        return [];
    }
    if (!isJsonArray(messages)) {
        throw new TypeError('Plugin system_requirements.messages must be an array');
    }
    if (!messages.length) {
        return [];
    }
    const normalizedMessages = normalizeRequirementStringList(messages, 'Plugin system_requirements.messages').filter(Boolean);
    const normalizedAction = toTrimmedString(action);
    const blockingActions = systemRequirements['blocking_actions'];
    if (!isNullOrUndefined(blockingActions) && !isJsonArray(blockingActions)) {
        throw new TypeError('Plugin system_requirements.blocking_actions must be an array');
    }
    if (isJsonArray(blockingActions) && blockingActions.length) {
        const normalizedBlockingActions = normalizeRequirementStringList(blockingActions, 'Plugin system_requirements.blocking_actions').filter(Boolean);
        if (!normalizedBlockingActions.includes(normalizedAction)) {
            return [];
        }
    }
    return normalizedMessages;
};

export { getPluginSystemRequirementMessages };
