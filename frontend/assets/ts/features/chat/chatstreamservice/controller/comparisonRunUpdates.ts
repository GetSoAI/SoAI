/* SoAI - Comparison-variant stream update identity [frontend/assets/ts/features/chat/chatstreamservice/controller/comparisonRunUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveNormalizedComparisonModelIdsFromModelSettings } from '@core/chat/comparisonModels.ts';
import { buildComparisonVariantRequestId, resolveComparisonGroupRequestId } from '@features/chat/chatstreamservice/comparisonRequestIdentity.ts';
import type { ConversationStreamState, StreamUpdate } from '@features/chat/chatstreamservice/controller/types.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

const resolveConversationComparisonVariantCount = (conversation: Conversation): number => {
    const modelSettings = conversation.modelSettings;
    const primaryModelId = modelSettings.model?.trim() || null;
    const comparisonModelIds = resolveNormalizedComparisonModelIdsFromModelSettings({
        modelSettings,
        primaryModelId
    });
    return comparisonModelIds.length + 1;
};

const syncActiveComparisonRunFromUpdate = (state: ConversationStreamState, conversation: Conversation, update: StreamUpdate, updateRequestId: string | null): void => {
    if (update.status !== 'streaming' || updateRequestId === null) {
        return;
    }
    const variantCount = resolveConversationComparisonVariantCount(conversation);
    if (variantCount <= 1 || update.modelVariantIndex < 0 || update.modelVariantIndex >= variantCount) {
        return;
    }
    const groupRequestId = resolveComparisonGroupRequestId(updateRequestId);
    const existing = state.comparisonRun;
    if (existing && existing.assistantTurnTimestamp === update.assistantTurnTimestamp && existing.variantCount === variantCount && existing.groupRequestId === groupRequestId) {
        return;
    }
    state.comparisonRun = {
        groupRequestId,
        assistantTurnTimestamp: update.assistantTurnTimestamp,
        variantCount,
        aborting: false
    };
};

const isExpectedComparisonVariantUpdate = (state: ConversationStreamState, update: StreamUpdate, updateRequestId: string | null): boolean => {
    if (update.status !== 'streaming' || updateRequestId === null || state.comparisonRun === null) {
        return false;
    }
    const comparisonRun = state.comparisonRun;
    if (comparisonRun.aborting || update.assistantTurnTimestamp !== comparisonRun.assistantTurnTimestamp) {
        return false;
    }
    if (update.modelVariantIndex < 0 || update.modelVariantIndex >= comparisonRun.variantCount) {
        return false;
    }
    return updateRequestId === buildComparisonVariantRequestId(comparisonRun.groupRequestId, update.modelVariantIndex);
};

const matchesActiveStreamUpdateIdentity = (state: ConversationStreamState, update: StreamUpdate, updateRequestId: string | null): boolean => {
    if (updateRequestId === null) {
        return false;
    }
    if (updateRequestId === state.requestId) {
        return true;
    }
    const comparisonRun = state.comparisonRun;
    if (comparisonRun === null) {
        return false;
    }
    if (update.assistantTurnTimestamp !== comparisonRun.assistantTurnTimestamp) {
        return false;
    }
    if (update.modelVariantIndex < 0 || update.modelVariantIndex >= comparisonRun.variantCount) {
        return false;
    }
    return resolveComparisonGroupRequestId(updateRequestId) === comparisonRun.groupRequestId;
};

const isFinalComparisonVariantTerminal = (state: ConversationStreamState, update: StreamUpdate, updateRequestId: string | null): boolean => {
    if (update.status === 'streaming' || updateRequestId === null) {
        return false;
    }
    const comparisonRun = state.comparisonRun;
    if (comparisonRun === null || comparisonRun.aborting || update.assistantTurnTimestamp !== comparisonRun.assistantTurnTimestamp) {
        return false;
    }
    const finalVariantIndex = comparisonRun.variantCount - 1;
    if (finalVariantIndex < 1 || update.modelVariantIndex !== finalVariantIndex) {
        return false;
    }
    return updateRequestId === buildComparisonVariantRequestId(comparisonRun.groupRequestId, finalVariantIndex);
};

export { isExpectedComparisonVariantUpdate, isFinalComparisonVariantTerminal, matchesActiveStreamUpdateIdentity, resolveConversationComparisonVariantCount, syncActiveComparisonRunFromUpdate };
