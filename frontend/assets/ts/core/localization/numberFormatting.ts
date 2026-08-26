/* SoAI - Shared localization number formatting [frontend/assets/ts/core/localization/numberFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocalizationSnapshot } from '@core/localization/runtime.ts';

const formatLocalizedNumber = (value: number, options: Intl.NumberFormatOptions = {}): string => new Intl.NumberFormat(getLocalizationSnapshot().locale, options).format(value);

const formatInvariantNumber = (value: number, options: Intl.NumberFormatOptions = {}): string => new Intl.NumberFormat('en-US', { ...options, useGrouping: false }).format(value);

const formatInvariantCompactNumber = (value: number): string => formatInvariantNumber(value, { notation: 'compact', maximumFractionDigits: 1 });

export { formatInvariantCompactNumber, formatInvariantNumber, formatLocalizedNumber };
