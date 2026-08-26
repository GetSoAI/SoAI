/* SoAI - Chat activity duration responsive display policy [frontend/assets/ts/features/chat/message/messageview/activityDurationDisplay.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ChatActivityDurationDisplayMode = 'all' | 'expandedOnly';
type ChatActivityDurationExpansionState = 'collapsed' | 'expanded';

const resolveActivityDurationDisplayMode = (viewportWidth: number, compactBreakpointPx: number): ChatActivityDurationDisplayMode => {
    return viewportWidth <= compactBreakpointPx ? 'expandedOnly' : 'all';
};

const shouldRenderActivityDuration = (displayMode: ChatActivityDurationDisplayMode, expansionState: ChatActivityDurationExpansionState): boolean => {
    return displayMode === 'all' || expansionState === 'expanded';
};

const renderSettledActivityDurationAttribute = (escapeAttribute: (value: string) => string, status: string, durationMs: number | undefined): string => {
    if (status === 'running' || typeof durationMs !== 'number' || !Number.isFinite(durationMs) || durationMs < 0) {
        return '';
    }
    return ` data-settled-duration-ms="${escapeAttribute(String(Math.floor(durationMs)))}"`;
};

export { renderSettledActivityDurationAttribute, resolveActivityDurationDisplayMode, shouldRenderActivityDuration };
export type { ChatActivityDurationDisplayMode, ChatActivityDurationExpansionState };
