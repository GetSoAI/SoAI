/* SoAI - Charts feature history chart sync gate [frontend/assets/ts/features/charts/historyChartSyncGate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const chartControlSyncSequences = new WeakMap<WeakKey, number>();

const nextChartControlSyncSequence = (host: WeakKey): number => {
    const next = (chartControlSyncSequences.get(host) ?? 0) + 1;
    chartControlSyncSequences.set(host, next);
    return next;
};

const isCurrentChartControlSync = (host: WeakKey, sequence: number): boolean => chartControlSyncSequences.get(host) === sequence;

const invalidateChartControlSync = (host: WeakKey): void => {
    nextChartControlSyncSequence(host);
};

export { invalidateChartControlSync, isCurrentChartControlSync, nextChartControlSyncSequence };
