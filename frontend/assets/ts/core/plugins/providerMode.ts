/* SoAI - Shared plugins provider mode [frontend/assets/ts/core/plugins/providerMode.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';

type ProviderModeValue = 'none' | 'user_managed' | 'plugin_managed';
type ProviderModeInput = string | null | undefined;

interface ProviderModeCarrier {
    capabilities?: {
        externalProviderMode?: ProviderModeInput;
    } | null;
}

const PROVIDER_MODE: Readonly<{ NONE: 'none'; USER_MANAGED: 'user_managed'; PLUGIN_MANAGED: 'plugin_managed' }> = Object.freeze({
    NONE: 'none',
    USER_MANAGED: 'user_managed',
    PLUGIN_MANAGED: 'plugin_managed'
});

const resolveProviderMode = (plugin: ProviderModeCarrier | null | undefined): ProviderModeValue => {
    const candidate = plugin?.capabilities?.externalProviderMode;
    if (!isString(candidate)) {
        return PROVIDER_MODE.NONE;
    }
    const normalized = candidate.trim().toLowerCase();
    if (normalized === PROVIDER_MODE.USER_MANAGED) {
        return PROVIDER_MODE.USER_MANAGED;
    }
    if (normalized === PROVIDER_MODE.PLUGIN_MANAGED) {
        return PROVIDER_MODE.PLUGIN_MANAGED;
    }
    return PROVIDER_MODE.NONE;
};

const hasExplicitProviderMode = (plugin: ProviderModeCarrier | null | undefined): boolean => {
    const candidate = plugin?.capabilities?.externalProviderMode;
    return isString(candidate) && candidate.trim().length > 0;
};

export { PROVIDER_MODE, hasExplicitProviderMode, resolveProviderMode };
export type { ProviderModeValue };
