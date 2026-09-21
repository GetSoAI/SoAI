/* SoAI - Chat activity duration responsive display policy [frontend/assets/ts/features/chat/message/messageview/activityDurationDisplay.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ChatActivityDurationDisplayMode = 'all' | 'expandedOnly' | 'settledOnly';
type ChatActivityDurationExpansionState = 'collapsed' | 'expanded';

const resolveActivityDurationDisplayMode = (viewportWidth: number, compactBreakpointPx: number, showElapsedTime = true): ChatActivityDurationDisplayMode => {
    if (!showElapsedTime) {
        return 'settledOnly';
    }
    if (viewportWidth <= compactBreakpointPx) {
        return 'expandedOnly';
    }
    return 'all';
};

const isSettledActivityDurationStatus = (status: string): boolean => status !== 'running' && status !== 'pending';

const shouldRenderActivityDuration = (displayMode: ChatActivityDurationDisplayMode, expansionState: ChatActivityDurationExpansionState, status: string): boolean => {
    if (displayMode === 'all') {
        return true;
    }
    if (displayMode === 'expandedOnly') {
        return expansionState === 'expanded';
    }
    return isSettledActivityDurationStatus(status);
};

const shouldAnimateSettledActivityDuration = (displayMode: ChatActivityDurationDisplayMode, status: string): boolean => displayMode === 'settledOnly' && isSettledActivityDurationStatus(status);

const renderSettledActivityDurationAttribute = (escapeAttribute: (value: string) => string, status: string, durationMs: number | undefined): string => {
    if (!isSettledActivityDurationStatus(status) || typeof durationMs !== 'number' || !Number.isFinite(durationMs) || durationMs < 0) {
        return '';
    }
    return ` data-settled-duration-ms="${escapeAttribute(String(Math.floor(durationMs)))}"`;
};

export { renderSettledActivityDurationAttribute, resolveActivityDurationDisplayMode, shouldAnimateSettledActivityDuration, shouldRenderActivityDuration };
export type { ChatActivityDurationDisplayMode, ChatActivityDurationExpansionState };
