/* SoAI - Prompts page contracts constants [frontend/assets/ts/pages/prompts/contracts/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { daysToMs } from '@core/time/durations.ts';

const DAY_IN_MS = daysToMs(1);
const DOWNLOAD_SELECTION_PREFIX = 'SoAI-selected-prompts';
const DEFAULT_GROUP_KEY = 'none';
const PROMPTS_CARD_IDENTITY_ATTRIBUTE = 'data-prompt-id';

const DATE_GROUP_KEYS: ReadonlyArray<string> = Object.freeze(['today', 'yesterday', 'thisWeek', 'thisMonth', 'older']);

export { DAY_IN_MS, DEFAULT_GROUP_KEY, DOWNLOAD_SELECTION_PREFIX, DATE_GROUP_KEYS, PROMPTS_CARD_IDENTITY_ATTRIBUTE };
