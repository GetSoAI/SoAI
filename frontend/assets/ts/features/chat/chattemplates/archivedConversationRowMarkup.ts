/* SoAI - Archived conversation row markup [frontend/assets/ts/features/chat/chattemplates/archivedConversationRowMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { COLOR_GROUPS, normalizeColor } from '@core/ui/colorToolkitBase.ts';
import { CONVERSATION_TITLE_MAX_LENGTH } from '@features/chat/chatConstants.ts';
import { sanitizeTitle } from '@features/chat/conversationFormatting.ts';
import type { ArchivedConversationSummary } from '@features/chat/storage/storageModels.ts';

interface ArchivedConversationRowLabels {
    open: string;
    unarchive: string;
    delete: string;
    color: string;
    colorPicker: string;
    favorite: string;
    rename: string;
    save: string;
    cancel: string;
    archived: string;
    messaging: string;
    untitled: string;
}

interface ArchivedConversationRowOptions {
    conversations: readonly ArchivedConversationSummary[];
    selectedIds: ReadonlySet<string>;
    renamingId: string | null;
    renameDraft: string;
    colorPickerOpenId: string | null;
    formatDate: (timestamp: number) => string;
    sanitizer: SanitizerApi;
    archiveIconHtml: TrustedHtml;
    messagingIconHtml: TrustedHtml;
    deleteIconHtml: TrustedHtml;
    favoriteIconHtml: TrustedHtml;
    editIconHtml: TrustedHtml;
    saveIconHtml: TrustedHtml;
    cancelIconHtml: TrustedHtml;
    colorLabels: Readonly<Record<string, string>>;
    labels: ArchivedConversationRowLabels;
}

type AttributeEncoder = (value: string) => string;

const buildColorSwatchesMarkup = (options: ArchivedConversationRowOptions, attr: AttributeEncoder, normalizedColor: string | null): string => {
    return COLOR_GROUPS.map((group) => {
        const groupValue = group.value === null ? null : normalizeColor(group.value);
        const isSelected = groupValue === normalizedColor;
        const selectedClass = isSelected ? ' is-selected' : '';
        const label = attr(options.colorLabels[group.key] ?? '');
        const colorAttr = group.value === null ? '' : attr(group.value);
        return `<button type="button" class="chat-color-option chat-color-option-${group.key}${selectedClass}" data-action="archive:select-color" data-color="${colorAttr}" aria-label="${label}" data-tooltip="${label}" aria-pressed="${isSelected ? 'true' : 'false'}"></button>`;
    }).join('');
};

const buildColorPickerMarkup = (options: ArchivedConversationRowOptions, attr: AttributeEncoder, conversation: ArchivedConversationSummary): string => {
    const normalizedColor = normalizeColor(conversation.color);
    const favoriteClass = conversation.isFavorite ? ' is-selected' : '';
    const favoritePressed = conversation.isFavorite ? 'true' : 'false';
    const renameButton = `<button type="button" class="chat-color-option chat-color-option-rename" data-action="archive:rename-start" aria-label="${attr(options.labels.rename)}" data-tooltip="${attr(options.labels.rename)}">${renderIconSlot(options.editIconHtml)}</button>`;
    const unarchiveButton = `<button type="button" class="chat-color-option chat-color-option-archive" data-action="archive:unarchive" aria-label="${attr(options.labels.unarchive)}" data-tooltip="${attr(options.labels.unarchive)}">${renderIconSlot(options.archiveIconHtml)}</button>`;
    const favoriteButton = `<button type="button" class="chat-color-option chat-color-option-favorite${favoriteClass}" data-action="archive:favorite" aria-label="${attr(options.labels.favorite)}" data-tooltip="${attr(options.labels.favorite)}" aria-pressed="${favoritePressed}">${renderIconSlot(options.favoriteIconHtml)}</button>`;
    return `<div class="chat-conversation-color-picker soai-dropdown-menu" role="radiogroup" aria-label="${attr(options.labels.colorPicker)}"><div class="chat-color-picker-colors">${buildColorSwatchesMarkup(options, attr, normalizedColor)}</div><div class="chat-color-picker-actions">${renameButton}${unarchiveButton}${favoriteButton}</div></div>`;
};

const buildRowActionsMarkup = (options: ArchivedConversationRowOptions, attr: AttributeEncoder, conversation: ArchivedConversationSummary, renaming: boolean): string => {
    if (renaming) {
        const saveButton = `<button type="button" class="archived-conversation-action ui-icon-button ui-icon-button-small ui-variant-neutral" data-action="archive:rename-save" aria-label="${attr(options.labels.save)}" data-tooltip="${attr(options.labels.save)}">${renderIconSlot(options.saveIconHtml)}</button>`;
        const cancelButton = `<button type="button" class="archived-conversation-action ui-icon-button ui-icon-button-small ui-variant-neutral" data-action="archive:rename-cancel" aria-label="${attr(options.labels.cancel)}" data-tooltip="${attr(options.labels.cancel)}">${renderIconSlot(options.cancelIconHtml)}</button>`;
        return `${saveButton}${cancelButton}`;
    }
    const colorTrigger = `<button type="button" class="archived-conversation-action archived-conversation-color-trigger ui-icon-button ui-icon-button-small" data-action="archive:open-color-picker" aria-label="${attr(options.labels.color)}" data-tooltip="${attr(options.labels.color)}"></button>`;
    const deleteButton = `<button type="button" class="archived-conversation-action archived-conversation-delete ui-icon-button ui-icon-button-small" data-action="archive:delete" aria-label="${attr(options.labels.delete)}" data-tooltip="${attr(options.labels.delete)}">${renderIconSlot(options.deleteIconHtml)}</button>`;
    const picker = options.colorPickerOpenId === conversation.id ? buildColorPickerMarkup(options, attr, conversation) : '';
    return `${colorTrigger}${deleteButton}${picker}`;
};

const buildArchivedConversationRowsMarkup = (options: ArchivedConversationRowOptions): TrustedHtml => {
    const attr: AttributeEncoder = (value: string): string => options.sanitizer.attribute(value);
    const html = (value: string): string => options.sanitizer.html(value);
    const rows = options.conversations
        .map((conversation) => {
            const id = attr(conversation.id);
            const title = html(sanitizeTitle(conversation.title) || options.labels.untitled);
            const selectedClass = options.selectedIds.has(conversation.id) ? ' is-selected' : '';
            const renaming = options.renamingId === conversation.id;
            const pickerOpenClass = options.colorPickerOpenId === conversation.id ? ' color-picker-open' : '';
            const favoriteAttr = conversation.isFavorite ? ' data-is-favorite="true"' : '';
            const colorAttr = conversation.color ? ` data-conversation-color="${attr(conversation.color)}"` : '';
            const titleMarkup = renaming ? `<div class="archived-conversation-title-editor"><input type="text" class="archived-conversation-title-input" value="${attr(options.renameDraft)}" aria-label="${attr(options.labels.save)}" maxlength="${CONVERSATION_TITLE_MAX_LENGTH}"></div>` : `<div class="archived-conversation-title">${title}</div>`;
            const messagingIndicator = conversation.isMessaging ? `<span class="archived-conversation-messaging-icon" aria-label="${attr(options.labels.messaging)}" data-tooltip="${attr(options.labels.messaging)}">${renderIconSlot(options.messagingIconHtml)}</span>` : '';
            const informationContent = `${titleMarkup}<div class="archived-conversation-meta"><span class="conversation-date">${html(options.formatDate(conversation.updatedAt))}</span><span class="archived-conversation-icon" aria-label="${attr(options.labels.archived)}">${renderIconSlot(options.archiveIconHtml)}</span>${messagingIndicator}<span>${String(conversation.messageCount)}</span></div>`;
            const informationMarkup = renaming ? `<div class="archived-conversation-info">${informationContent}</div>` : `<button type="button" class="archived-conversation-info" data-action="archive:open" aria-label="${attr(options.labels.open)}" data-tooltip="${attr(options.labels.open)}">${informationContent}</button>`;
            const actions = buildRowActionsMarkup(options, attr, conversation, renaming);
            return `<div class="archived-conversation-item${selectedClass}${pickerOpenClass}" data-id="${id}"${favoriteAttr}${colorAttr}><div class="archived-conversation-select"><input type="checkbox" class="archived-conversation-select-input" data-action="archive:select" ${options.selectedIds.has(conversation.id) ? 'checked' : ''} aria-label="${attr(options.labels.open)}"></div>${informationMarkup}<div class="archived-conversation-actions">${actions}</div></div>`;
        })
        .join('');
    return toTrustedUiHtml(rows);
};

export { buildArchivedConversationRowsMarkup };
export type { ArchivedConversationRowOptions };
