/* SoAI - Provider modal record normalization [frontend/assets/ts/features/models/modals/providersmodal/providerRecords.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { formatNullableEpochMsMinuteWithFallback } from '@core/primitives/dateTime.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isAllowedStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { ExternalProviderRecord } from '@core/api/contracts/pluginProviderContracts.ts';
import type { ProviderAvailabilityPresentation, ProviderAvailabilityStatus, ProviderAvailabilityTone, ProviderData } from '@features/models/modals/providersmodal/contracts.ts';

const PROVIDER_AVAILABILITY_STATUSES: readonly ProviderAvailabilityStatus[] = Object.freeze(['UNCHECKED', 'OK', 'ERROR', 'TIMEOUT', 'VALIDATING', 'AUTH_REQUIRED']);

const readProviderAvailabilityStatus = (value: JsonValue | undefined): ProviderAvailabilityStatus => {
    const normalized = toTrimmedString(value);
    if (!normalized) {
        return 'UNCHECKED';
    }
    if (isAllowedStringValue(normalized, PROVIDER_AVAILABILITY_STATUSES)) {
        return normalized;
    }
    throw new Error('Provider availability status is invalid.');
};

const resolveProviderAvailabilityLabel = (status: ProviderAvailabilityStatus): string => {
    if (status === 'OK') return i18n.t('models.modal.providers.status.ok');
    if (status === 'ERROR') return i18n.t('models.modal.providers.status.error');
    if (status === 'TIMEOUT') return i18n.t('models.modal.providers.status.timeout');
    if (status === 'AUTH_REQUIRED') return i18n.t('models.modal.providers.status.authRequired');
    if (status === 'VALIDATING') return i18n.t('models.modal.providers.status.validating');
    return i18n.t('models.modal.providers.status.unchecked');
};

const resolveProviderAvailabilityTone = (status: ProviderAvailabilityStatus): ProviderAvailabilityTone => {
    if (status === 'OK') return 'success';
    if (status === 'ERROR' || status === 'TIMEOUT') return 'danger';
    if (status === 'AUTH_REQUIRED') return 'warning';
    if (status === 'VALIDATING') return 'loading';
    return 'neutral';
};

const buildProviderAvailabilityPresentation = (status: ProviderAvailabilityStatus, lastError: string | null, lastCheckedAtMs: number | null): ProviderAvailabilityPresentation => {
    const tone = resolveProviderAvailabilityTone(status);
    return {
        statusLabel: resolveProviderAvailabilityLabel(status),
        statusClassName: `provider-status-badge provider-status-badge--${tone}`,
        checkedLabel: formatNullableEpochMsMinuteWithFallback(lastCheckedAtMs, i18n.t('common.notAvailable')),
        errorLabel: lastError ?? i18n.t('common.notAvailable'),
        tone
    };
};

const normalizeProviderRecord = (record: ExternalProviderRecord): ProviderData => {
    const lastStatus = readProviderAvailabilityStatus(record.lastStatus);
    const lastError = record.lastError;
    const lastCheckedAtMs = record.lastCheckedAtMs;
    return {
        id: readRequiredTrimmedStringValue(record.id, 'Provider id'),
        name: readRequiredTrimmedStringValue(record.name, 'Provider name'),
        pluginName: readRequiredTrimmedStringValue(record.pluginName, 'Provider plugin name'),
        revision: record.revision,
        apiUrl: readRequiredTrimmedStringValue(record.apiUrl, 'Provider apiUrl'),
        lastStatus: lastStatus,
        lastError: lastError,
        lastCheckedAtMs: lastCheckedAtMs,
        availability: buildProviderAvailabilityPresentation(lastStatus, lastError, lastCheckedAtMs)
    };
};

export { normalizeProviderRecord };
