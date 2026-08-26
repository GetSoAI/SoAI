/* SoAI - Charts feature data transforms constants [frontend/assets/ts/features/charts/datatransforms/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const MIN_RETENTION_MINUTES = 15;
const DEFAULT_TIME_RANGES = Object.freeze([15, 30, 60, 120, 180, 360, 720, 1440, 2880, 10080, 43200, 129600, 259200, 525600, 1051200, 2628000, 5256000]);
const DEFAULT_CANDLE_INTERVALS = Object.freeze([1, 3, 5, 15, 30, 60, 120, 240, 360, 720, 1440]);
const ONE_MINUTE_MS = 60_000;

export { DEFAULT_CANDLE_INTERVALS, DEFAULT_TIME_RANGES, MIN_RETENTION_MINUTES, ONE_MINUTE_MS };
