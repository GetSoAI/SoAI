/* SoAI - Conversation export cover data builder [frontend/assets/ts/features/chat/conversationexport/coverData.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import { resolveMessageTitle } from '@features/chat/messageBuilding.ts';
import { resolveConversationExportOriginLabel } from '@features/chat/conversationexport/conversationOrigin.ts';
import { clampCoverFieldText, COVER_OUTLINE_PREVIEW_MAX_LENGTH, COVER_OUTLINE_ROLE_MAX_LENGTH, resolveConversationExportOutlineCapacity } from '@features/chat/conversationexport/coverContract.ts';
import { buildCoverSummaryItems, type ConversationExportModelResolver, type ConversationExportSummaryItem } from '@features/chat/conversationexport/coverMetrics.ts';
import { resolveConversationExportTurns, type ConversationExportTurn, type ExportCoverTurnKind } from '@features/chat/conversationexport/turnModel.ts';
import { resolveConversationExportUserSenderLabel } from '@features/chat/message/senderLabel.ts';

type ConversationExportOutlineEntry = {
    index: number;
    kind: ExportCoverTurnKind;
    role: string;
    preview: string;
};

type ConversationExportCoverData = {
    origin: string;
    summaryItems: ConversationExportSummaryItem[];
    outline: ConversationExportOutlineEntry[];
};

const OUTLINE_OVERFLOW_ROLE = '…';

const outlineRoleLabel = (conversation: ConversationContract, turn: ConversationExportTurn): string => {
    switch (turn.kind) {
        case 'user':
            return resolveConversationExportUserSenderLabel({
                conversation,
                message: turn.previewMessage,
                fallbackLabel: i18n.t('chat.export.pdf.outline.role.user')
            });
        case 'assistant':
            return i18n.t('chat.export.pdf.outline.role.assistant');
        case 'tool':
            return i18n.t('chat.export.pdf.outline.role.tool');
        case 'other':
            return i18n.t('chat.export.pdf.outline.role.other');
    }
};

const outlinePreview = (turn: ConversationExportTurn): string => {
    const base = turn.previewMessage !== null ? resolveMessageTitle(turn.previewMessage, COVER_OUTLINE_PREVIEW_MAX_LENGTH) : '';
    if (turn.variantCount > 1) {
        const variants = i18n.t('chat.export.pdf.comparisonTurn', { count: turn.variantCount });
        return clampCoverFieldText(base ? `${variants} — ${base}` : variants, COVER_OUTLINE_PREVIEW_MAX_LENGTH);
    }
    return clampCoverFieldText(base ? base : i18n.t('chat.export.pdf.outline.empty'), COVER_OUTLINE_PREVIEW_MAX_LENGTH);
};

const countRemainingMessages = (turns: readonly ConversationExportTurn[], fromIndex: number): number => {
    let count = 0;
    for (let index = fromIndex; index < turns.length; index += 1) {
        const turn = turns[index];
        if (turn !== undefined && (turn.kind === 'user' || turn.kind === 'assistant')) {
            count += 1;
        }
    }
    return count;
};

const buildOutline = (conversation: ConversationContract, turns: readonly ConversationExportTurn[], capacity: number): ConversationExportOutlineEntry[] => {
    if (capacity <= 0) {
        return [];
    }
    const outline: ConversationExportOutlineEntry[] = [];
    const overflowing = turns.length > capacity;
    const limit = overflowing ? capacity - 1 : turns.length;
    for (let index = 0; index < limit; index += 1) {
        const turn = turns[index];
        if (turn === undefined) {
            break;
        }
        outline.push({
            index: index + 1,
            kind: turn.kind,
            role: clampCoverFieldText(outlineRoleLabel(conversation, turn), COVER_OUTLINE_ROLE_MAX_LENGTH),
            preview: outlinePreview(turn)
        });
    }
    if (overflowing) {
        const remaining = countRemainingMessages(turns, limit);
        outline.push({
            index: limit + 1,
            kind: 'other',
            role: OUTLINE_OVERFLOW_ROLE,
            preview: i18n.t('chat.export.pdf.outline.more', { count: remaining })
        });
    }
    return outline;
};

const buildConversationExportCoverData = (conversation: ConversationContract, options: { defaultModel: string | null; resolveModel: ConversationExportModelResolver; exportedAt: Date }): ConversationExportCoverData => {
    const turns = resolveConversationExportTurns(conversation);
    const origin = resolveConversationExportOriginLabel(conversation);
    const summaryItems = buildCoverSummaryItems(turns, conversation, options.defaultModel, options.resolveModel, options.exportedAt);
    const capacity = resolveConversationExportOutlineCapacity({ summaryItemCount: summaryItems.length, hasOriginLine: origin.length > 0 });
    return {
        origin,
        summaryItems,
        outline: buildOutline(conversation, turns, capacity)
    };
};

export { buildConversationExportCoverData };
export type { ConversationExportCoverData, ConversationExportOutlineEntry, ConversationExportSummaryItem };
export type { ConversationExportModelCategory, ConversationExportModelDescriptor, ConversationExportModelResolver } from '@features/chat/conversationexport/coverMetrics.ts';
