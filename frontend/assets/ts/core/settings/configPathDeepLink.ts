/* SoAI - Settings configuration path deep link contract [frontend/assets/ts/core/settings/configPathDeepLink.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const SETTINGS_CONFIG_PATH_QUERY_KEY = 'setting';
const SETTINGS_TAB_QUERY_KEY = 'tab';

interface SettingsConfigPathDeepLinkOptions {
    tab: string;
    configPath: string;
}

const buildSettingsConfigPathDeepLinkQuery = (options: SettingsConfigPathDeepLinkOptions): Record<string, string> => {
    const configPath = toTrimmedString(options.configPath);
    if (!configPath) {
        throw new Error('Settings configuration path deep link requires a configuration path');
    }
    const query: Record<string, string> = {};
    const tab = toTrimmedString(options.tab);
    if (tab) {
        query[SETTINGS_TAB_QUERY_KEY] = tab;
    }
    query[SETTINGS_CONFIG_PATH_QUERY_KEY] = configPath;
    return query;
};

const resolveSettingsConfigPathFromQuery = (parameters: Record<string, JsonValue | null | undefined> | null | undefined): string | null => {
    if (!isObject(parameters)) {
        return null;
    }
    const configPath = toTrimmedString(parameters[SETTINGS_CONFIG_PATH_QUERY_KEY]);
    return configPath ? configPath : null;
};

export { buildSettingsConfigPathDeepLinkQuery, resolveSettingsConfigPathFromQuery, SETTINGS_CONFIG_PATH_QUERY_KEY };
export type { SettingsConfigPathDeepLinkOptions };
