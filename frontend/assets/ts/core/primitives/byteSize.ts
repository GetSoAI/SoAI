/* SoAI - Shared byte-size formatting primitive [frontend/assets/ts/core/primitives/byteSize.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatByteSize, formatInvariantNumber } from '@core/localization/public.ts';
import { isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';

const formatBytes = (bytes: number | null | undefined, decimals: number = 1): string => {
    if (isNullOrUndefined(bytes)) return i18n.t('common.unknown');
    const numericBytes = Number(bytes);
    if (!isFiniteNumber(numericBytes)) throw new Error('Bytes value must be numeric');
    return formatByteSize(numericBytes, Math.max(0, decimals));
};

const formatKilobytesFromBytes = (bytes: number, decimals: number = 1): string => {
    const numericBytes = Number(bytes);
    if (!isFiniteNumber(numericBytes)) throw new Error('Bytes value must be numeric');
    return `${formatInvariantNumber(numericBytes / 1024, { maximumFractionDigits: Math.max(0, decimals) })} KB`;
};

const formatGigabytesAsStorageUnit = (gigabytes: number, decimals: number = 2): string => {
    const numericGigabytes = Number(gigabytes);
    if (!isFiniteNumber(numericGigabytes)) throw new Error('Gigabytes value must be numeric');
    return numericGigabytes >= 1024 ? `${formatInvariantNumber(numericGigabytes / 1024, { maximumFractionDigits: Math.max(0, decimals) })} TB` : `${formatInvariantNumber(numericGigabytes, { maximumFractionDigits: Math.max(0, decimals) })} GB`;
};

export { formatBytes, formatGigabytesAsStorageUnit, formatKilobytesFromBytes };
