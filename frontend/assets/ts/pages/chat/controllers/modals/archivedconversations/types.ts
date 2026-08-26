/* SoAI - Archived conversations modal types [frontend/assets/ts/pages/chat/controllers/modals/archivedconversations/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ArchivedConversationSummary, ArchivedConversationsCursor, ChatPageApi } from '@features/chat/public.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ArchivedConversationsModalHost extends PageFeedbackOwnerHost {
    pageContext: { sanitizer: SanitizerApi };
    api: ChatPageApi;
    getCachedIcon(name: IconName, options?: IconOptions): TrustedHtml;
    openConversationEnsuringLoaded(conversationId: string): void;
    deleteArchivedConversations(conversationIds: readonly string[]): Promise<readonly string[]>;
    refreshSidebarConversationList(): Promise<void>;
}

interface ArchivedConversationsModalRefs {
    root: HTMLElement;
    searchInput: HTMLInputElement;
    scrollContainer: HTMLElement;
    listContainer: HTMLElement;
    statusElement: HTMLElement;
    totalElement: HTMLElement;
    selectedElement: HTMLElement;
    selectButton: HTMLButtonElement;
    batchActionsContainer: HTMLElement;
    batchUnarchiveButton: HTMLButtonElement;
    batchDeleteButton: HTMLButtonElement;
    exitSelectButton: HTMLButtonElement;
}

interface ArchivedConversationsModalState {
    conversations: ArchivedConversationSummary[];
    totalCount: number;
    nextCursor: ArchivedConversationsCursor | null;
    query: string;
    loading: boolean;
    requestVersion: number;
    searchMode: boolean;
    selectedIds: Set<string>;
    selectionActive: boolean;
    renamingId: string | null;
    renameDraft: string;
    colorPickerOpenId: string | null;
}

type ArchivedConversationAction = 'archive:batch-delete' | 'archive:batch-unarchive' | 'archive:delete' | 'archive:enter-select-mode' | 'archive:exit-select-mode' | 'archive:favorite' | 'archive:open' | 'archive:open-color-picker' | 'archive:rename-cancel' | 'archive:rename-save' | 'archive:rename-start' | 'archive:select' | 'archive:select-color' | 'archive:unarchive';

export type { ArchivedConversationAction, ArchivedConversationsModalHost, ArchivedConversationsModalRefs, ArchivedConversationsModalState };
