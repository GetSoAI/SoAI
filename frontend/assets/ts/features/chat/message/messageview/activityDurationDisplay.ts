/* SoAI - Chat activity duration responsive display policy [frontend/assets/ts/features/chat/message/messageview/activityDurationDisplay.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ChatActivityDurationDisplayMode = 'all' | 'settledOnly';

const resolveActivityDurationDisplayMode = (showElapsedTime: boolean): ChatActivityDurationDisplayMode => (showElapsedTime ? 'all' : 'settledOnly');

const isSettledActivityDurationStatus = (status: string): boolean => status !== 'running' && status !== 'pending';

const shouldRenderActivityDuration = (displayMode: ChatActivityDurationDisplayMode, status: string): boolean => displayMode === 'all' || isSettledActivityDurationStatus(status);

const shouldAnimateSettledActivityDuration = (displayMode: ChatActivityDurationDisplayMode, status: string): boolean => displayMode === 'settledOnly' && isSettledActivityDurationStatus(status);

const renderSettledActivityDurationAttribute = (escapeAttribute: (value: string) => string, status: string, durationMs: number | undefined): string => {
    if (!isSettledActivityDurationStatus(status) || typeof durationMs !== 'number' || !Number.isFinite(durationMs) || durationMs < 0) {
        return '';
    }
    return ` data-settled-duration-ms="${escapeAttribute(String(Math.floor(durationMs)))}"`;
};

export { renderSettledActivityDurationAttribute, resolveActivityDurationDisplayMode, shouldAnimateSettledActivityDuration, shouldRenderActivityDuration };
export type { ChatActivityDurationDisplayMode };
