/* SoAI - Automation page calendar constants [frontend/assets/ts/pages/automation/widgets/calendar/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { minutesToMs } from '@core/time/durations.ts';

const AUTOMATION_DEFAULT_DISPLAY_DURATION_MS = minutesToMs(20);
const AUTOMATION_DEFAULT_HOUR_HEIGHT_PX = 64;
const AUTOMATION_DEFAULT_MONTH_MAX_ZONES_PER_DAY = 4;

export { AUTOMATION_DEFAULT_DISPLAY_DURATION_MS, AUTOMATION_DEFAULT_HOUR_HEIGHT_PX, AUTOMATION_DEFAULT_MONTH_MAX_ZONES_PER_DAY };
