/* SoAI - Settings page preferences service [frontend/assets/ts/pages/settings/controllers/preferences/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildLanguageOptions } from '@core/languageservice/languageOptions.ts';
import { clampFiniteNumber } from '@core/primitives/clampNumber.ts';

const normalizeNotificationDuration = (value: number): number => clampFiniteNumber(value, 5, 1, 10);

export { buildLanguageOptions, normalizeNotificationDuration };
