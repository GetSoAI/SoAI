/* SoAI - Shared chart motion timing [frontend/assets/ts/core/animations/chartMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';

const SERIES_TRANSITION_MS = 240;

const scaleChartAnimationDurationMs = (durationMs: number, element: Element): number => (element.ownerDocument.visibilityState === 'hidden' ? 0 : scaleAnimationDurationMs(durationMs, element));

const easeOutCubic = (progress: number): number => 1 - (1 - Math.min(1, Math.max(0, progress))) ** 3;

export { easeOutCubic, scaleChartAnimationDurationMs, SERIES_TRANSITION_MS };
