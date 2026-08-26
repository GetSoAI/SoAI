/* SoAI - Plugins feature clone service [frontend/assets/ts/features/plugins/modals/clone/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPortablePluginIdentifier } from '@core/plugins/portablePluginIdentifier.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { CloneState } from '@features/plugins/modals/clone/types.ts';

const createInitialCloneState = (): CloneState => ({
    currentCloningPlugin: null
});

const isPluginCloneSupported = (plugin: PluginRecord): boolean => {
    const capabilities = plugin.capabilities ?? null;
    const supportsCloningValue = capabilities ? capabilities.supportsCloning : null;
    return supportsCloningValue === true;
};

const resolvePluginDisplayName = (plugin: PluginRecord, formatPluginName: (name: string) => string): string => {
    const pluginName = toTrimmedString(plugin.name);
    if (!pluginName) {
        throw new Error('CloneManager requires a plugin name to resolve display name');
    }
    const displayNameRaw = toTrimmedString(plugin.displayName);
    return displayNameRaw ? displayNameRaw : formatPluginName(pluginName);
};

const resolveCloneTargetName = (useCustomName: boolean, rawInput: string): string | null => {
    if (!useCustomName) {
        return null;
    }
    const trimmed = toTrimmedString(rawInput);
    return trimmed ? trimmed : null;
};

const isValidCloneTargetName = (targetName: string): boolean => isPortablePluginIdentifier(targetName);

const createPluginCloneOperationKey = (pluginName: string): string => {
    const normalized = toTrimmedString(pluginName);
    if (!normalized) throw new Error('Clone operation key requires a plugin name');
    return `plugin:${normalized}:clone`;
};

export { createInitialCloneState, createPluginCloneOperationKey, isPluginCloneSupported, isValidCloneTargetName, resolveCloneTargetName, resolvePluginDisplayName };
