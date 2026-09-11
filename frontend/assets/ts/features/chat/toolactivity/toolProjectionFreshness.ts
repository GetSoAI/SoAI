/* SoAI - Tool projection replacement freshness [frontend/assets/ts/features/chat/toolactivity/toolProjectionFreshness.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNonNegativeInteger } from '@core/typeGuards.ts';
import type { ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { isTerminalToolActivityStatus } from '@features/chat/toolactivity/toolActivityStatus.ts';
import { compareToolResultMediaHydration } from '@features/chat/toolactivity/toolResultMediaHydration.ts';

const compareProjectionCounter = (existingValue: number | undefined, incomingValue: number | undefined): number | null => {
    if (!isNonNegativeInteger(existingValue) || !isNonNegativeInteger(incomingValue)) {
        return null;
    }
    if (incomingValue < existingValue) {
        return -1;
    }
    if (incomingValue > existingValue) {
        return 1;
    }
    return 0;
};

const compareProjectionFreshness = (existing: ToolActivityItem, incoming: ToolActivityItem): number => {
    const sequenceComparison = compareProjectionCounter(existing.lastLiveSequence, incoming.lastLiveSequence);
    if (sequenceComparison !== null && sequenceComparison !== 0) {
        return sequenceComparison;
    }
    const revisionComparison = compareProjectionCounter(existing.liveRevision, incoming.liveRevision);
    if (revisionComparison !== null && revisionComparison !== 0) {
        return revisionComparison;
    }
    const eventTimeComparison = compareProjectionCounter(existing.lastLiveEventAtMs, incoming.lastLiveEventAtMs);
    if (eventTimeComparison !== null && eventTimeComparison !== 0) {
        return eventTimeComparison;
    }
    return 0;
};

const compareProjectionImageHydration = (existing: ToolActivityItem, incoming: ToolActivityItem): number => {
    return compareToolResultMediaHydration(existing.result, incoming.result, { toolLeafName: incoming.toolName });
};

const isActiveToolStatus = (status: ToolActivityItem['status']): boolean => status === 'pending' || status === 'running';

const shouldReplaceToolProjection = (existing: ToolActivityItem, incoming: ToolActivityItem): boolean => {
    if (isTerminalToolActivityStatus(existing.status) && isActiveToolStatus(incoming.status)) {
        return false;
    }
    if (isActiveToolStatus(existing.status) && isTerminalToolActivityStatus(incoming.status)) {
        return true;
    }
    const freshnessComparison = compareProjectionFreshness(existing, incoming);
    if (freshnessComparison < 0) {
        return false;
    }
    if (freshnessComparison > 0) {
        return true;
    }
    return compareProjectionImageHydration(existing, incoming) >= 0;
};

export { shouldReplaceToolProjection };
