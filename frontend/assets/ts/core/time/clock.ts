/* SoAI - Shared time clock [frontend/assets/ts/core/time/clock.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveServerTimeMs } from '@core/time/serverTimeClock.ts';

const monotonicMs = (): number => performance.now();
const serverEpochMs = (): number => resolveServerTimeMs();
const wallClockMs = (): number => Date.now();

export { monotonicMs, serverEpochMs, wallClockMs };
