/* SoAI - Shared localization validation [frontend/assets/ts/core/localization/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ClockFormatPreference, DateFormatPreference, MeasurementUnitsPreference, RegionalLocalePreference } from '@core/localization/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const isClockFormatPreference = (value: JsonValue | null | undefined): value is ClockFormatPreference => value === '24h' || value === '12h';

const isRegionalLocalePreference = (value: JsonValue | null | undefined): value is RegionalLocalePreference => value === 'auto' || value === 'browser' || value === 'en-US' || value === 'en-GB' || value === 'it-IT';

const isDateFormatPreference = (value: JsonValue | null | undefined): value is DateFormatPreference => value === 'auto' || value === 'us' || value === 'eu' || value === 'iso';

const isMeasurementUnitsPreference = (value: JsonValue | null | undefined): value is MeasurementUnitsPreference => value === 'auto' || value === 'metric' || value === 'imperial';

export { isClockFormatPreference, isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference };
