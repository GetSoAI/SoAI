/* SoAI - Settings feature quota modal payload [frontend/assets/ts/features/settings/apikeys/quotaModalPayload.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import type { ApiKeyQuotaUpdateRequest } from '@core/api/contracts/apiKeyQuotaContracts.ts';
import type { ApiKeyQuotaMode } from '@core/settings/contracts.ts';
import { readRequiredPositiveIntegerTextValue } from '@core/types/payloadNumberReaders.ts';
import { setControlDisabledStateForEach } from '@core/ui/controls/disabledState.ts';

const readOptionalPositiveInt = (input: HTMLInputElement): number | null => {
    const trimmed = readTrimmedInputValue(input);
    if (!trimmed) {
        return null;
    }
    return readRequiredPositiveIntegerTextValue(trimmed, 'Value must be a positive integer');
};

const coerceQuotaMode = (value: string): ApiKeyQuotaMode => {
    const normalized = toTrimmedLower(value);
    if (normalized === 'none' || normalized === 'tokens' || normalized === 'requests') {
        return normalized;
    }
    throw new TypeError('Quota mode is invalid');
};

const buildQuotaUpdatePayload = (
    mode: ApiKeyQuotaMode,
    fields: {
        hourlyLimit: number | null;
        hourlyWindowHours: number | null;
        dailyLimit: number | null;
        weeklyLimit: number | null;
        monthlyLimit: number | null;
    }
): ApiKeyQuotaUpdateRequest => {
    if (mode === 'none') {
        return { mode };
    }

    const payload: ApiKeyQuotaUpdateRequest = { mode };
    if ((fields.hourlyLimit === null) !== (fields.hourlyWindowHours === null)) {
        throw new TypeError('Hourly quota requires both limit and window hours.');
    }
    if (fields.hourlyLimit !== null && fields.hourlyWindowHours !== null) {
        payload.hourly = { limitUnits: fields.hourlyLimit, windowHours: fields.hourlyWindowHours };
    }
    if (fields.dailyLimit !== null) {
        payload.daily = { limitUnits: fields.dailyLimit };
    }
    if (fields.weeklyLimit !== null) {
        payload.weekly = { limitUnits: fields.weeklyLimit };
    }
    if (fields.monthlyLimit !== null) {
        payload.monthly = { limitUnits: fields.monthlyLimit };
    }
    return payload;
};

const setInputsEnabled = (inputs: HTMLInputElement[], enabled: boolean): void => {
    setControlDisabledStateForEach(inputs, !enabled);
};

export { buildQuotaUpdatePayload, coerceQuotaMode, readOptionalPositiveInt, setInputsEnabled };
