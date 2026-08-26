/* SoAI - Shared active streaming assistant message resolution [frontend/assets/ts/features/chat/message/activeStreamingAssistantMessage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { compareChatStreamMessageOrderIdentities } from '@features/chat/chatstreamservice/streamIdentity.ts';
import type { ChatTurnAdmissionStreamIdentity } from '@features/chat/chatstreamservice/types.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';
import { resolveMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { isAssistantMessageRole } from '@features/chat/message/messageRole.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ActiveComparisonRun = {
    assistantTurnTimestamp: number;
    variantCount: number;
};

type ActiveStreamingAssistantMeta = {
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

type ActiveStreamingAssistantSelection = {
    domIds: ReadonlySet<string>;
    meta: ActiveStreamingAssistantMeta | null;
};

type TerminalRenderPendingPredicate = (conversationId: string, message: ChatMessage) => boolean;

type ActiveStreamingAssistantResolutionArguments = {
    isConversationStreaming: boolean;
    activeComparisonRun: ActiveComparisonRun | null;
    activeStreamIdentity: ChatTurnAdmissionStreamIdentity | null;
    isTerminalRenderPending?: TerminalRenderPendingPredicate;
};

const EMPTY_SELECTION: ActiveStreamingAssistantSelection = { domIds: new Set<string>(), meta: null };

const resolveLastUserMessageIndex = (messages: readonly ChatMessage[]): number => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        if (messages[index]?.role === 'user') {
            return index;
        }
    }
    return -1;
};

const resolveEligibleAssistantIdentity = (message: ChatMessage) => {
    if (!isAssistantMessageRole(message)) {
        return null;
    }
    return resolveAssistantMessageIdentity({
        assistantTimestamp: message.timestamp,
        assistantTurnTimestamp: message.assistantTurnAtMs,
        modelVariantIndex: message.modelVariantIndex
    });
};

const identityMatchesActiveStream = (identity: NonNullable<ReturnType<typeof resolveAssistantMessageIdentity>>, activeStreamIdentity: ChatTurnAdmissionStreamIdentity): boolean => {
    return compareChatStreamMessageOrderIdentities(identity, activeStreamIdentity) === 0;
};

const resolveActiveStreamingAssistantSelection = (conversation: ConversationContract | null, inputArguments: ActiveStreamingAssistantResolutionArguments): ActiveStreamingAssistantSelection => {
    if (!inputArguments.isConversationStreaming || conversation === null) {
        return EMPTY_SELECTION;
    }
    const conversationId = normalizeConversationId(conversation.id);
    if (!conversationId) {
        return EMPTY_SELECTION;
    }
    const messages = conversation.messages;
    const activeStreamIdentity = inputArguments.activeStreamIdentity;
    const alignedComparisonTurn = activeStreamIdentity !== null && inputArguments.activeComparisonRun?.assistantTurnTimestamp === activeStreamIdentity.assistantTurnTimestamp;
    const lastUserMessageIndex = resolveLastUserMessageIndex(messages);
    const selected: Array<{ message: ChatMessage; index: number; identity: NonNullable<ReturnType<typeof resolveAssistantMessageIdentity>> }> = [];

    for (const [index, message] of messages.entries()) {
        const identity = resolveEligibleAssistantIdentity(message);
        if (identity === null) {
            continue;
        }
        const isTerminal = hasTerminalAssistantState(message);
        const isTerminalPending = inputArguments.isTerminalRenderPending?.(conversationId, message) === true;
        if (activeStreamIdentity !== null) {
            const isExactActiveStream = identityMatchesActiveStream(identity, activeStreamIdentity);
            if (alignedComparisonTurn ? identity.assistantTurnTimestamp !== activeStreamIdentity.assistantTurnTimestamp : !isExactActiveStream) {
                continue;
            }
            if (isTerminal && !isExactActiveStream && !isTerminalPending) {
                continue;
            }
            if (isTerminal && index < lastUserMessageIndex) {
                continue;
            }
        } else {
            if ((isTerminal && !isTerminalPending) || conversation.history?.hasNewer === true || index < lastUserMessageIndex) {
                continue;
            }
            if (inputArguments.activeComparisonRun !== null && identity.assistantTurnTimestamp !== inputArguments.activeComparisonRun.assistantTurnTimestamp) {
                continue;
            }
        }
        selected.push({ message, index, identity });
    }

    if (selected.length === 0) {
        return EMPTY_SELECTION;
    }
    const latestSelected = selected[selected.length - 1];
    if (latestSelected === undefined) {
        return EMPTY_SELECTION;
    }
    const targetTurnTimestamp = activeStreamIdentity?.assistantTurnTimestamp ?? inputArguments.activeComparisonRun?.assistantTurnTimestamp ?? latestSelected.identity.assistantTurnTimestamp;
    const comparisonSelection = inputArguments.activeComparisonRun?.assistantTurnTimestamp === targetTurnTimestamp && (activeStreamIdentity === null || alignedComparisonTurn);
    const finalSelection = comparisonSelection ? selected.filter((candidate) => candidate.identity.assistantTurnTimestamp === targetTurnTimestamp) : [latestSelected];
    const domIds = new Set(finalSelection.map((candidate) => resolveMessageDomId(candidate.message, candidate.index)));
    const primary = finalSelection.find((candidate) => activeStreamIdentity !== null && identityMatchesActiveStream(candidate.identity, activeStreamIdentity)) ?? finalSelection[finalSelection.length - 1] ?? null;
    return {
        domIds,
        meta: primary
            ? {
                  assistantTurnTimestamp: primary.identity.assistantTurnTimestamp,
                  modelVariantIndex: primary.identity.modelVariantIndex
              }
            : null
    };
};

export { resolveActiveStreamingAssistantSelection };
export type { ActiveComparisonRun, ActiveStreamingAssistantMeta, ActiveStreamingAssistantResolutionArguments, ActiveStreamingAssistantSelection, TerminalRenderPendingPredicate };
