/* SoAI - Shared time durations [frontend/assets/ts/core/time/durations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3_600;
const SECONDS_PER_DAY = 86_400;
const MILLISECONDS_PER_SECOND = 1_000;
const MILLISECONDS_PER_MINUTE = 60_000;
const MILLISECONDS_PER_HOUR = 3_600_000;
const MILLISECONDS_PER_DAY = 86_400_000;

const secondsToMs = (seconds: number): number => seconds * MILLISECONDS_PER_SECOND;
const minutesToMs = (minutes: number): number => minutes * MILLISECONDS_PER_MINUTE;
const hoursToMs = (hours: number): number => hours * MILLISECONDS_PER_HOUR;
const daysToMs = (days: number): number => days * MILLISECONDS_PER_DAY;
const minutesToSeconds = (minutes: number): number => minutes * SECONDS_PER_MINUTE;
const hoursToSeconds = (hours: number): number => hours * SECONDS_PER_HOUR;
const daysToSeconds = (days: number): number => days * SECONDS_PER_DAY;
const msToSeconds = (milliseconds: number): number => milliseconds / MILLISECONDS_PER_SECOND;
const msToMinutes = (milliseconds: number): number => milliseconds / MILLISECONDS_PER_MINUTE;

export { daysToMs, daysToSeconds, hoursToMs, hoursToSeconds, minutesToMs, minutesToSeconds, msToMinutes, msToSeconds, secondsToMs };
