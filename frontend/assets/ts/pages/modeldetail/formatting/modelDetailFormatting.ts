/* SoAI - Model detail page formatting implementation [frontend/assets/ts/pages/modeldetail/formatting/modelDetailFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatNullableEpochMsSecondOrNull } from '@core/primitives/dateTime.ts';
import { capitalize, formatTitleFromId } from '@core/primitives/text.ts';
import { resolveHttpUrl } from '@core/security/public.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

const maskModelDetailApiUrl = (url: string | null | undefined): string | null => {
    if (!url) return null;
    try {
        const resolved = resolveHttpUrl(url) ?? url;
        const parsed = new URL(resolved);
        return `${parsed.protocol}//${parsed.host}${parsed.pathname ? '/...' : ''}`;
    } catch (error) {
        ensureError(error);
        return url.length > 30 ? `${url.substring(0, 30)}...` : url;
    }
};

const formatModelDetailDefaultValue = (value: JsonValue, valueType: string): string | null => {
    if (value === null || value === undefined) return null;
    if (valueType === 'boolean') return value ? 'true' : 'false';
    if (valueType === 'array') {
        return isArray(value) && value.length > 0 ? JSON.stringify(value) : null;
    }
    if (valueType === 'object') {
        return isObject(value) && Object.keys(value).length > 0 ? JSON.stringify(value) : null;
    }
    return valueType === 'string' && value === '' ? null : String(value);
};

const formatModelDetailDateTime = (timestampMs: number | null | undefined): string | null => formatNullableEpochMsSecondOrNull(timestampMs);

const extractCleanModelIdentifier = (identifier: string | undefined): string | undefined => {
    if (!identifier) return identifier;
    const parts = identifier.split('/');
    return parts.length > 1 ? parts.slice(1).join('/') : identifier;
};

const formatModelDetailPluginName = (record: PluginRecord | null, pluginName: string): string => {
    const displayRaw = (isString(record?.displayName) && record.displayName) || (isString(record?.name) && record.name) || pluginName;
    return formatTitleFromId(displayRaw) || displayRaw;
};

const formatModelDetailTypeLabel = (model: ModelRecord): string => {
    const type = isString(model.type) ? model.type.trim() : '';
    if (type === 'virtual') {
        return `${i18n.t('modelDetail.cards.identity.virtual')} (${model.strategy || i18n.t('models.types.unknown')})`;
    }
    if (type === 'local') {
        return i18n.t('models.types.local');
    }
    return type ? capitalize(type) : i18n.t('models.types.unknown');
};

export { extractCleanModelIdentifier, formatModelDetailDateTime, formatModelDetailDefaultValue, formatModelDetailPluginName, formatModelDetailTypeLabel, maskModelDetailApiUrl };
