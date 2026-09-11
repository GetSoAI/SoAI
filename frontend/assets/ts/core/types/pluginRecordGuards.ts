/* SoAI - Shared frontend types plugin record guards [frontend/assets/ts/core/types/pluginRecordGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const isOptionalString = (value: JsonValue | undefined): boolean => value === undefined || typeof value === 'string';

const isOptionalNullableString = (value: JsonValue | undefined): boolean => value === null || isOptionalString(value);

const isOptionalBoolean = (value: JsonValue | undefined): boolean => value === undefined || typeof value === 'boolean';

const isOptionalRecord = (value: JsonValue | undefined): boolean => value === undefined || value === null || isJsonObject(value);

const hasPluginIdentity = (value: JsonObject): boolean => typeof value['name'] === 'string' || typeof value['id'] === 'string';

const isPluginRecord = <T>(value: T): value is T & PluginRecord => {
    if (!isJsonObject(value)) {
        return false;
    }
    if (!hasPluginIdentity(value)) {
        return false;
    }
    if (!isOptionalString(value['name']) || !isOptionalString(value['displayName']) || !isOptionalString(value['id']) || !isOptionalString(value['state']) || !isOptionalNullableString(value['logoRevision'])) {
        return false;
    }
    if (!isOptionalBoolean(value['isEnabled']) || !isOptionalBoolean(value['isAvailable']) || !isOptionalBoolean(value['permanentlyDisabled']) || !isOptionalBoolean(value['isPersistent']) || !isOptionalBoolean(value['isBuiltin']) || !isOptionalBoolean(value['userEnabledOnce']) || !isOptionalBoolean(value['circuitBreakerWasEnabled'])) {
        return false;
    }
    return isOptionalRecord(value['circuitBreaker']) && isOptionalRecord(value['capabilities']) && isOptionalRecord(value['incompatibility']);
};

const isNamedPluginRecord = <T>(value: T): value is T & PluginRecord & { name: string } => isPluginRecord(value) && typeof value.name === 'string' && value.name.trim().length > 0;

export { isNamedPluginRecord, isPluginRecord };
