/* SoAI - Atomic assistant stream snapshot transaction [frontend/assets/ts/features/chat/chatstreamservice/assistantSnapshotTransaction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { createAssistantTimelineIndexState, type AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import { updateAssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexUpdate.ts';
import { hasTerminalThinkingActivityStatusRegression } from '@features/chat/assistanteventtimeline/activityState.ts';
import { preserveAssistantCollapsedOverrideRecords } from '@features/chat/assistanteventtimeline/collapsedOverrideRecords.ts';
import type { AssistantEventTimelineItem, ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveAssistantTimelineProgress } from '@features/chat/chatstreamservice/assistantStreamMessageState.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { requireAssistantMessageVariantIdentity } from '@features/chat/message/assistantMessageIdentity.ts';
import { resolveDurableAssistantTerminalState } from '@features/chat/message/assistantTerminalState.ts';

type PreparedAssistantSnapshot = {
    indexState: AssistantTimelineIndexState;
    message: ChatMessage;
    revision: number;
    usagePreview: TokenUsageSnapshot | null;
};

const resolveLatestAssistantTimelineUsagePreview = (message: ChatMessage): TokenUsageSnapshot | null => {
    let resolved: TokenUsageSnapshot | null = null;
    for (const event of message.assistantEventTimeline ?? []) {
        if (event.payload.usagePreview !== undefined) resolved = event.payload.usagePreview;
    }
    return resolved;
};

const nonTextTimelineEventsAreSemanticallyEqual = (existing: ChatMessage, incoming: ChatMessage): boolean => {
    const existingTimeline = existing.assistantEventTimeline ?? [];
    const incomingTimeline = incoming.assistantEventTimeline ?? [];
    let existingIndex = 0;
    let incomingIndex = 0;
    while (true) {
        while (existingTimeline[existingIndex]?.eventType === 'assistant_text_delta') existingIndex += 1;
        while (incomingTimeline[incomingIndex]?.eventType === 'assistant_text_delta') incomingIndex += 1;
        const existingEvent: AssistantEventTimelineItem | undefined = existingTimeline[existingIndex];
        const incomingEvent: AssistantEventTimelineItem | undefined = incomingTimeline[incomingIndex];
        if (existingEvent === undefined || incomingEvent === undefined) return existingEvent === incomingEvent;
        if (existingEvent.sequence !== incomingEvent.sequence || existingEvent.assistantRevision !== incomingEvent.assistantRevision || existingEvent.eventType !== incomingEvent.eventType || !deepEqual(existingEvent.payload, incomingEvent.payload)) {
            return false;
        }
        existingIndex += 1;
        incomingIndex += 1;
    }
};

const equalRevisionSnapshotCanReplace = (existing: ChatMessage, incoming: ChatMessage): boolean => {
    const existingTerminalState = resolveDurableAssistantTerminalState(existing);
    const incomingTerminalState = resolveDurableAssistantTerminalState(incoming);
    if (existingTerminalState !== null) {
        if (incomingTerminalState === null) return false;
        if (incomingTerminalState !== existingTerminalState) throw new Error('Equal-revision assistant snapshots disagree on terminal state.');
        return true;
    }
    if (incomingTerminalState !== null) return true;
    if (!deepEqual(existing.content, incoming.content) || !nonTextTimelineEventsAreSemanticallyEqual(existing, incoming)) {
        throw new Error('Equal-revision assistant snapshots must be semantically equivalent.');
    }
    return true;
};

const prepareAssistantSnapshot = (session: ChatStreamSession, incoming: ChatMessage): PreparedAssistantSnapshot | null => {
    const identity = requireAssistantMessageVariantIdentity(incoming, 'Assistant stream snapshot');
    if (incoming.timestamp !== session.assistantTimestamp || identity.assistantTurnTimestamp !== session.assistantTurnTimestamp || identity.modelVariantIndex !== session.modelVariantIndex) {
        throw new Error('Assistant stream snapshot identity does not match the active session.');
    }
    const candidate: ChatMessage = { ...incoming };
    preserveAssistantCollapsedOverrideRecords(session.assistantMessage, candidate);
    const progress = resolveAssistantTimelineProgress(candidate);
    if (progress.assistantRevision < session.assistantRevision) return null;
    if (progress.assistantRevision === session.assistantRevision && !equalRevisionSnapshotCanReplace(session.assistantMessage, candidate)) return null;
    if (hasTerminalThinkingActivityStatusRegression(session.assistantMessage, candidate)) throw new Error('Assistant stream snapshot regressed a terminal thinking lifecycle.');
    const indexState = createAssistantTimelineIndexState();
    updateAssistantTimelineIndexState(indexState, candidate);
    return { indexState, message: candidate, revision: progress.assistantRevision, usagePreview: resolveLatestAssistantTimelineUsagePreview(candidate) ?? session.usagePreview };
};

const commitAssistantSnapshot = (session: ChatStreamSession, prepared: PreparedAssistantSnapshot): void => {
    session.assistantMessage = prepared.message;
    session.assistantRevision = prepared.revision;
    session.assistantTimelineIndexState = prepared.indexState;
    session.usagePreview = prepared.usagePreview;
};

export { commitAssistantSnapshot, prepareAssistantSnapshot, resolveLatestAssistantTimelineUsagePreview };
export type { PreparedAssistantSnapshot };
