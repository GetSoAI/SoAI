/* SoAI - Chat attach modal browse result rendering [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseResultsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentCollectionResponse, KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { resolveFileEntryIconName } from '@core/fileexplorerbrowser/entryIconResolution.ts';
import { resolveFileEntryTypeLabel } from '@core/fileexplorerbrowser/entryTypeLabels.ts';
import type { FileBrowserEntry } from '@core/fileexplorerbrowser/types.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isImageMimeType } from '@core/media/mimeTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { SortDirection, SortState } from '@core/ui/tables/sortableTable.ts';
import { i18n } from '@core/i18n/index.ts';

type ChatAttachBrowseSortColumn = 'name' | 'type' | 'size' | 'modified';

type ChatAttachBrowseSortState = SortState<ChatAttachBrowseSortColumn>;

type ChatAttachBrowseResult =
    | {
          type: 'workspace';
          key: string;
          title: string;
          status: string;
          chip: string;
          iconName: IconName;
          typeLabel: string;
          sizeLabel: string;
          sortSize: number;
          modifiedLabel: string;
          sortModified: number;
          path: string;
          entryType: 'file' | 'folder';
      }
    | {
          type: 'knowledge';
          key: string;
          title: string;
          status: string;
          chip: string;
          iconName: IconName;
          typeLabel: string;
          sizeLabel: string;
          sortSize: number;
          modifiedLabel: string;
          sortModified: number;
          sourceConversationId: string;
          knowledgeAttachmentId: string;
          visibleCount: number;
          completedCount: number;
          useMaxItems: number;
      };

const CHAT_ATTACH_BROWSE_SORT_COLUMNS: readonly ChatAttachBrowseSortColumn[] = ['name', 'type', 'size', 'modified'];

const CHAT_ATTACH_BROWSE_SORT_COLUMN_DEFAULT_DIRECTIONS: Readonly<Record<ChatAttachBrowseSortColumn, SortDirection>> = {
    name: 'asc',
    type: 'asc',
    size: 'desc',
    modified: 'desc'
};

const isImageMime = (value: string): boolean => isImageMimeType(value.toLowerCase());

const resolveKnowledgeItemsLabel = (count: number): string => {
    if (count === 1) {
        return i18n.t('chat.attachModal.browseKnowledgeItems.one', { count });
    }
    return i18n.t('chat.attachModal.browseKnowledgeItems.other', { count });
};

const createWorkspaceResult = (entry: FileBrowserEntry): ChatAttachBrowseResult => {
    const chip = entry.isDirectory ? i18n.t('chat.attachModal.browseChipLiveFolder') : isImageMime(entry.mimeType) ? i18n.t('chat.attachModal.browseChipImage') : i18n.t('chat.attachModal.browseChipLiveFile');
    const sizeLabel = entry.isDirectory ? '-' : formatBytes(entry.size, 1);
    return {
        type: 'workspace',
        key: `workspace:${entry.path}`,
        title: entry.name || entry.path,
        status: entry.path,
        chip,
        iconName: resolveFileEntryIconName(entry),
        typeLabel: resolveFileEntryTypeLabel(entry.typeId),
        sizeLabel,
        sortSize: entry.size,
        modifiedLabel: entry.modifiedAt,
        sortModified: entry.modifiedAtTimestamp,
        path: entry.path,
        entryType: entry.isDirectory ? 'folder' : 'file'
    };
};

const readCompletedCount = (value: KnowledgeAttachmentSummary): number => value.statusCounts['completed'] ?? 0;

const parseKnowledgeResult = (value: KnowledgeAttachmentSummary, useMaxItems: number): ChatAttachBrowseResult | null => {
    if (value.visibleCount < 1) return null;
    const sourceLabel = value.sourceType || i18n.t('chat.attachModal.browseKnowledgeSource');
    const sortModified = value.updatedAtMs;
    const modifiedLabel = sortModified > 0 ? i18n.formatDate(new Date(sortModified), { year: 'numeric', month: 'short', day: '2-digit' }) : '-';
    const sizeLabel = resolveKnowledgeItemsLabel(value.visibleCount);
    return {
        type: 'knowledge',
        key: `knowledge:${value.knowledgeAttachmentId}`,
        title: value.title,
        status: sourceLabel,
        chip: i18n.t('chat.attachModal.browseChipKnowledge'),
        iconName: 'book-open',
        typeLabel: i18n.t('chat.attachModal.browseKnowledgeSource'),
        sizeLabel,
        sortSize: value.visibleCount,
        modifiedLabel,
        sortModified,
        sourceConversationId: value.convId,
        knowledgeAttachmentId: value.knowledgeAttachmentId,
        visibleCount: value.visibleCount,
        completedCount: readCompletedCount(value),
        useMaxItems
    };
};

const parseReusableKnowledgeResults = (payload: KnowledgeAttachmentCollectionResponse): ChatAttachBrowseResult[] => {
    const useMaxItems = payload.useMaxItems !== null && payload.useMaxItems > 0 ? payload.useMaxItems : 1;
    const results: ChatAttachBrowseResult[] = [];
    for (const item of payload.items) {
        const result = parseKnowledgeResult(item, useMaxItems);
        if (result !== null) {
            results.push(result);
        }
    }
    return results;
};

const compareText = (left: string, right: string, locale: string): number => left.localeCompare(right, locale, { sensitivity: 'base' });

const sortBrowseResults = (results: readonly ChatAttachBrowseResult[], sortState: ChatAttachBrowseSortState): ChatAttachBrowseResult[] => {
    const multiplier = sortState.direction === 'asc' ? 1 : -1;
    const locale = getCurrentLocale();
    return [...results].sort((left, right) => {
        switch (sortState.column) {
            case 'name':
                return multiplier * compareText(left.title, right.title, locale);
            case 'type': {
                const typeComparison = compareText(left.typeLabel, right.typeLabel, locale);
                if (typeComparison !== 0) {
                    return multiplier * typeComparison;
                }
                return compareText(left.title, right.title, locale);
            }
            case 'size':
                return multiplier * (left.sortSize - right.sortSize);
            case 'modified':
                return multiplier * (left.sortModified - right.sortModified);
        }
    });
};

const buildWorkspaceBrowseResults = (entries: readonly FileBrowserEntry[]): ChatAttachBrowseResult[] => entries.map((entry) => createWorkspaceResult(entry));

export { CHAT_ATTACH_BROWSE_SORT_COLUMN_DEFAULT_DIRECTIONS, CHAT_ATTACH_BROWSE_SORT_COLUMNS, buildWorkspaceBrowseResults, parseReusableKnowledgeResults, sortBrowseResults };
export type { ChatAttachBrowseResult, ChatAttachBrowseSortColumn, ChatAttachBrowseSortState };
