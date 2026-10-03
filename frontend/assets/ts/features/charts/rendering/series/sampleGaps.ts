/* SoAI - Chart sample gap classification [frontend/assets/ts/features/charts/rendering/series/sampleGaps.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isMissingSampleInterval = (previousTimestamp: number, currentTimestamp: number, expectedIntervalMs: number): boolean => {
    return Number.isFinite(previousTimestamp) && Number.isFinite(currentTimestamp) && Number.isFinite(expectedIntervalMs) && expectedIntervalMs > 0 && currentTimestamp - previousTimestamp > expectedIntervalMs * 1.5;
};

export { isMissingSampleInterval };
