/* SoAI - Running activity snapshot computation from running messages [frontend/assets/ts/features/chat/storage/runningActivitySnapshotComputation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ParsedRunningActivitySnapshot } from '@features/chat/storage/messageWindowPersistence.ts';
import type { ConversationRunningActivitySnapshot, MessageCursor, RunningActivityTargetSnapshot } from '@features/chat/storage/storageModels.ts';
import { resolveRunningActivitySummary, type RunningActivityTarget } from '@features/chat/toolactivity/runningActivitySummary.ts';

const isNonNegativeInteger = (value: number | string | null | undefined): value is number => {
    return typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) && value >= 0;
};

const resolveSnapshotMessageCursor = (message: ChatMessage): MessageCursor | null => {
    const id = message.id;
    const timestamp = message.timestamp;
    if (!isNonNegativeInteger(id) || !isNonNegativeInteger(timestamp)) {
        return null;
    }
    return { createdAtMs: timestamp, id };
};

const resolveTargetTurnIdentity = (message: ChatMessage): { assistantTurnAtMs: number; modelVariantIndex: number } | null => {
    const assistantTurnAtMs = message.assistantTurnAtMs;
    const modelVariantIndex = message.modelVariantIndex;
    if (!isNonNegativeInteger(assistantTurnAtMs) || !isNonNegativeInteger(modelVariantIndex)) {
        return null;
    }
    return { assistantTurnAtMs, modelVariantIndex };
};

const resolveSnapshotTarget = (message: ChatMessage, target: RunningActivityTarget): RunningActivityTargetSnapshot | null => {
    const cursor = resolveSnapshotMessageCursor(message);
    const identity = resolveTargetTurnIdentity(message);
    if (cursor === null || identity === null) {
        return null;
    }
    return {
        assistantTurnAtMs: identity.assistantTurnAtMs,
        modelVariantIndex: identity.modelVariantIndex,
        messageCursor: cursor,
        callId: target.callId,
        ancestorCallIds: target.ancestorCallIds,
        startedAtMs: target.startedAtMs
    };
};

const newerSnapshotTarget = (current: RunningActivityTargetSnapshot | null, candidate: RunningActivityTargetSnapshot): RunningActivityTargetSnapshot => {
    if (current === null || candidate.startedAtMs >= current.startedAtMs) {
        return candidate;
    }
    return current;
};

const computeRunningActivitySnapshot = (parsed: ParsedRunningActivitySnapshot, nowMs: number = serverEpochMs()): ConversationRunningActivitySnapshot => {
    let activityCount = 0;
    let backgroundActivityCount = 0;
    let backgroundSubagentCount = 0;
    let backgroundTarget: RunningActivityTargetSnapshot | null = null;
    let subagentCount = 0;
    let target: RunningActivityTargetSnapshot | null = null;
    for (const candidate of parsed.runningMessages) {
        if (!isChatMessage(candidate)) {
            continue;
        }
        const summary = resolveRunningActivitySummary(candidate, nowMs);
        activityCount += summary.activityCount;
        backgroundActivityCount += summary.backgroundActivityCount;
        backgroundSubagentCount += summary.backgroundSubagentCount;
        subagentCount += summary.subagentCount;
        if (summary.target !== null) {
            const streamTarget = resolveSnapshotTarget(candidate, summary.target);
            if (streamTarget !== null) {
                target = newerSnapshotTarget(target, streamTarget);
            }
        }
        if (summary.backgroundTarget !== null) {
            const activeBackgroundTarget = resolveSnapshotTarget(candidate, summary.backgroundTarget);
            if (activeBackgroundTarget !== null) {
                backgroundTarget = newerSnapshotTarget(backgroundTarget, activeBackgroundTarget);
            }
        }
    }
    return {
        convId: parsed.convId,
        activityCount: activityCount,
        backgroundActivityCount: backgroundActivityCount,
        backgroundSubagentCount: backgroundSubagentCount,
        backgroundTarget: backgroundTarget,
        subagentCount: subagentCount,
        target,
        lastModifiedAtMs: parsed.lastModifiedAtMs
    };
};

export { computeRunningActivitySnapshot };
