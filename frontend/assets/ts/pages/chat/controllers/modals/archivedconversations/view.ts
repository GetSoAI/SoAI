/* SoAI - Archived conversations modal rendering [frontend/assets/ts/pages/chat/controllers/modals/archivedconversations/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom } from '@core/dom/dom.ts';
import { syncSelectionActionVisibility, syncSelectionToolbarVisibility } from '@core/selection/toolbarVisibility.ts';
import { buildArchivedConversationRowsMarkup, CHAT_ICON_SIZE_XS } from '@features/chat/public.ts';
import { formatChatDate } from '@pages/chat/controllers/chatUiBehaviors.ts';
import type { ArchivedConversationsModalHost, ArchivedConversationsModalRefs, ArchivedConversationsModalState } from '@pages/chat/controllers/modals/archivedconversations/types.ts';

const renderArchivedConversationsModal = (host: ArchivedConversationsModalHost, refs: ArchivedConversationsModalRefs, state: ArchivedConversationsModalState): void => {
    refs.totalElement.textContent = i18n.t('chat.archive.totalCount', { count: state.totalCount });
    refs.selectedElement.textContent = i18n.t('chat.toolbar.selectedCount', { count: state.selectedIds.size });
    dom.setHTML(refs.selectButton, host.getCachedIcon('select', CHAT_ICON_SIZE_XS), { escape: false });
    dom.setHTML(refs.batchUnarchiveButton, host.getCachedIcon('archive', CHAT_ICON_SIZE_XS), { escape: false });
    dom.setHTML(refs.batchDeleteButton, host.getCachedIcon('delete', CHAT_ICON_SIZE_XS), { escape: false });
    dom.setHTML(refs.exitSelectButton, host.getCachedIcon('close', CHAT_ICON_SIZE_XS), { escape: false });
    refs.batchUnarchiveButton.disabled = state.selectedIds.size === 0;
    refs.batchDeleteButton.disabled = state.selectedIds.size === 0;
    syncSelectionActionVisibility(refs.batchUnarchiveButton, state.selectedIds.size > 0);
    syncSelectionActionVisibility(refs.batchDeleteButton, state.selectedIds.size > 0);
    syncSelectionToolbarVisibility(
        {
            modeTarget: refs.listContainer,
            toggleButton: refs.selectButton,
            batchActionsContainer: refs.batchActionsContainer,
            totalElements: [refs.totalElement],
            selectedElements: [refs.selectedElement]
        },
        state.selectionActive
    );
    dom.setHTML(
        refs.listContainer,
        buildArchivedConversationRowsMarkup({
            conversations: state.conversations,
            selectedIds: state.selectedIds,
            renamingId: state.renamingId,
            renameDraft: state.renameDraft,
            colorPickerOpenId: state.colorPickerOpenId,
            formatDate: formatChatDate,
            sanitizer: host.pageContext.sanitizer,
            archiveIconHtml: host.getCachedIcon('archive', CHAT_ICON_SIZE_XS),
            messagingIconHtml: host.getCachedIcon('send', CHAT_ICON_SIZE_XS),
            deleteIconHtml: host.getCachedIcon('close', CHAT_ICON_SIZE_XS),
            favoriteIconHtml: host.getCachedIcon('star', CHAT_ICON_SIZE_XS),
            editIconHtml: host.getCachedIcon('rename', CHAT_ICON_SIZE_XS),
            saveIconHtml: host.getCachedIcon('check', CHAT_ICON_SIZE_XS),
            cancelIconHtml: host.getCachedIcon('close', CHAT_ICON_SIZE_XS),
            colorLabels: {
                none: i18n.t('chat.colors.none'),
                red: i18n.t('chat.colors.red'),
                yellow: i18n.t('chat.colors.yellow'),
                purple: i18n.t('chat.colors.purple'),
                green: i18n.t('chat.colors.green'),
                blue: i18n.t('chat.colors.blue')
            },
            labels: {
                open: i18n.t('chat.archive.actions.open'),
                unarchive: i18n.t('chat.archive.actions.unarchive'),
                delete: i18n.t('chat.conversation.deleteTitle'),
                color: i18n.t('chat.conversation.colorPickerTitle'),
                colorPicker: i18n.t('chat.colors.pickerLabel'),
                favorite: i18n.t('chat.header.toggleFavorite'),
                rename: i18n.t('common.edit'),
                save: i18n.t('common.save'),
                cancel: i18n.t('common.cancel'),
                archived: i18n.t('chat.conversation.archived'),
                messaging: i18n.t('chat.conversation.messaging'),
                untitled: i18n.t('chat.conversation.untitled')
            }
        }),
        { escape: false }
    );
    if (state.loading) {
        refs.statusElement.textContent = i18n.t('chat.archive.loading');
    } else if (state.conversations.length === 0) {
        refs.statusElement.textContent = state.query ? i18n.t('chat.archive.noResults') : i18n.t('chat.archive.empty');
    } else {
        refs.statusElement.textContent = '';
    }
};

export { renderArchivedConversationsModal };
