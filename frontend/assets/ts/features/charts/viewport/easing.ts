/* SoAI - Charts feature motion easing [frontend/assets/ts/features/charts/viewport/easing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const SERIES_TRANSITION_MS = 240;

const easeOutCubic = (progress: number): number => 1 - (1 - Math.min(1, Math.max(0, progress))) ** 3;

export { easeOutCubic, SERIES_TRANSITION_MS };
