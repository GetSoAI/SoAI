/* SoAI - Archived conversations modal action contract [frontend/assets/ts/pages/chat/controllers/modals/archivedconversations/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import { requireConversationId } from '@features/chat/public.ts';
import type { ArchivedConversationAction } from '@pages/chat/controllers/modals/archivedconversations/types.ts';

const ARCHIVED_CONVERSATION_ACTIONS: readonly ArchivedConversationAction[] = ['archive:batch-delete', 'archive:batch-unarchive', 'archive:delete', 'archive:enter-select-mode', 'archive:exit-select-mode', 'archive:favorite', 'archive:open', 'archive:open-color-picker', 'archive:rename-cancel', 'archive:rename-save', 'archive:rename-start', 'archive:select', 'archive:select-color', 'archive:unarchive'];

const ARCHIVED_ROW_ACTIONS: readonly ArchivedConversationAction[] = ['archive:delete', 'archive:favorite', 'archive:open', 'archive:open-color-picker', 'archive:rename-cancel', 'archive:rename-save', 'archive:rename-start', 'archive:select', 'archive:select-color', 'archive:unarchive'];

type ArchivedConversationDeleteAction = Extract<ArchivedConversationAction, 'archive:delete' | 'archive:batch-delete'>;

type ArchivedConversationDeleteConfirmation = {
    title: () => string;
    message: (count: number) => string;
};

const ARCHIVED_CONVERSATION_DELETE_CONFIRMATION_MAP: Record<ArchivedConversationDeleteAction, ArchivedConversationDeleteConfirmation> = Object.freeze({
    'archive:delete': {
        title: () => i18n.t('chat.conversation.deleteTitle'),
        message: () => i18n.t('chat.conversation.deleteConfirm')
    },
    'archive:batch-delete': {
        title: () => i18n.t('chat.toolbar.batchDeleteTitle'),
        message: (count: number) => i18n.t('chat.toolbar.batchDeleteConfirm', { count })
    }
});

export type ArchivedConversationActionId = ArchivedConversationAction;

export const isArchivedConversationActionId = (value: string | undefined): value is ArchivedConversationActionId => {
    return isString(value) && ARCHIVED_CONVERSATION_ACTIONS.some((action) => action === value);
};

const isArchivedConversationAction = isArchivedConversationActionId;

const requireArchivedConversationActionId = (action: ArchivedConversationAction, value: string | null | undefined): string => {
    if (!ARCHIVED_ROW_ACTIONS.some((rowAction) => rowAction === action)) {
        return '';
    }
    return requireConversationId(value, 'Archived conversation action');
};

const resolveArchivedConversationActionErrorMessage = (action: ArchivedConversationAction): string => {
    if (action === 'archive:batch-unarchive' || action === 'archive:unarchive') {
        return i18n.t('chat.archive.errors.unarchiveFailed');
    }
    if (action === 'archive:batch-delete') {
        return i18n.t('chat.toolbar.batchDeleteFailed');
    }
    if (action === 'archive:delete') {
        return i18n.t('chat.conversation.deleteFailed');
    }
    if (action === 'archive:favorite') {
        return i18n.t('chat.conversation.favoriteUpdateFailed');
    }
    if (action === 'archive:rename-save') {
        return i18n.t('chat.conversation.renameFailed');
    }
    if (action === 'archive:select-color') {
        return i18n.t('chat.conversation.colorUpdateFailed');
    }
    return i18n.t('chat.archive.errors.loadFailed');
};

const resolveArchivedConversationDeleteConfirmation = (action: ArchivedConversationDeleteAction, count: number): { message: string; title: string } => {
    const confirmation = ARCHIVED_CONVERSATION_DELETE_CONFIRMATION_MAP[action];
    const normalizedCount = count <= 1 ? 1 : count;
    return {
        title: confirmation.title(),
        message: confirmation.message(normalizedCount)
    };
};

export { isArchivedConversationAction, requireArchivedConversationActionId, resolveArchivedConversationActionErrorMessage, resolveArchivedConversationDeleteConfirmation };
