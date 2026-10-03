/* SoAI - Shared chart history page windows [frontend/assets/ts/features/charts/historyPageWindow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface HistoryPageWindow {
    startTsMs: number;
    endTsMs: number;
}

const MAX_HISTORY_PAGE_REQUESTS = 512;

const resolveOlderHistoryPage = (endTsMs: number, targetStartTsMs: number, intervalMs: number, pointCap: number): HistoryPageWindow | null => {
    if (![endTsMs, targetStartTsMs, intervalMs, pointCap].every(Number.isFinite) || intervalMs < 1 || pointCap < 1) {
        throw new TypeError('Older history page requires finite timestamps, interval, and point cap');
    }
    const end = Math.floor(endTsMs);
    const targetStart = Math.max(0, Math.floor(targetStartTsMs));
    if (end <= targetStart) return null;
    const start = Math.max(targetStart, end - Math.floor(intervalMs) * Math.floor(pointCap));
    return start < end ? { startTsMs: start, endTsMs: end } : null;
};

const resolveHistoryPagePoints = (window: HistoryPageWindow, intervalMs: number): number => Math.max(1, Math.ceil((window.endTsMs - window.startTsMs) / intervalMs));

export { MAX_HISTORY_PAGE_REQUESTS, resolveHistoryPagePoints, resolveOlderHistoryPage };
export type { HistoryPageWindow };
