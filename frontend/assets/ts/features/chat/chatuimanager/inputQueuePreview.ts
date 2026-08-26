/* SoAI - Chat feature input queue preview [frontend/assets/ts/features/chat/chatuimanager/inputQueuePreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationInputState } from '@core/api/contracts/chatQueueDraftContracts.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { joinUiHtml, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { getElement, setElementVisibility } from '@features/chat/chatuimanager/dom.ts';
import { buildChatFilePreviewItemDocumentMarkup } from '@features/chat/chatuimanager/filePreviewItemDocumentMarkup.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

const resolveConversationInputStateLabel = (state: ConversationInputState): string => {
    if (state === 'materializing') {
        return i18n.t('chat.inputQueue.state.materializing');
    }
    if (state === 'running') {
        return i18n.t('chat.inputQueue.state.running');
    }
    if (state === 'input_required') {
        return i18n.t('chat.inputQueue.state.inputRequired');
    }
    return '';
};

const isConversationInputRemovable = (state: ConversationInputState): boolean => state === 'pending' || state === 'materializing';

const isConversationInputExecuting = (state: ConversationInputState): boolean => state === 'materializing' || state === 'running';

export function updateInputQueuePreview(context: ChatUIManagerContext): void {
    const inputQueuePreview = getElement(context, 'inputQueuePreview');
    if (!inputQueuePreview) {
        return;
    }

    const conversationInputs = context.dependencies.drafts.getConversationInputs();
    const validPrompts = isArray(conversationInputs)
        ? conversationInputs.filter((entry) => {
              if (!isObject(entry)) {
                  return false;
              }
              if (!isString(entry.inputId) || !entry.inputId.trim()) {
                  return false;
              }
              const inputType = entry.inputType;
              if (inputType !== 'prompt' && inputType !== 'steer') {
                  return false;
              }
              const text = toTrimmedString(entry.text);
              const attachmentContentValue = entry.attachmentContent;
              const attachmentCount = isArray(attachmentContentValue) ? attachmentContentValue.length : 0;
              if (!text && attachmentCount === 0) {
                  return false;
              }
              return true;
          })
        : [];

    if (validPrompts.length === 0) {
        context.dependencies.updateHTML(inputQueuePreview, '');
        setElementVisibility(context, 'inputQueuePreview', false);
        return;
    }

    const removeLabel = i18n.t('chat.attachments.removeTooltip');
    const removeIcon = context.dependencies.getCachedIcon('close', { size: 12, strokeWidth: 2.2 });

    const rows = validPrompts.map((entry) => {
        const inputType = entry.inputType === 'steer' ? 'steer' : 'prompt';
        const badgeText = inputType === 'steer' ? i18n.t('chat.inputQueue.badge.steer') : i18n.t('chat.inputQueue.badge.queued');
        const badgeClass = inputType === 'steer' ? 'input-queue-badge--steer' : 'input-queue-badge--queued';

        const conversationInputLabel = i18n.t('chat.attachments.conversationInputQueue');
        const nameHtml = uiHtml`<span class="input-queue-prompt-title">${uiText(conversationInputLabel)}</span><span class="input-queue-badge ${uiAttr(badgeClass)}">${uiText(badgeText)}</span>`;
        const normalized = isString(entry.text) ? entry.text.replace(/\s+/g, ' ').trim() : '';
        const truncated = normalized.length > 140 ? `${normalized.slice(0, 140).trim()}…` : normalized;
        const attachmentCount = isArray(entry.attachmentContent) ? entry.attachmentContent.length : 0;
        const attachmentSuffixText = attachmentCount > 0 ? i18n.t('chat.inputQueue.attachmentsCount', { count: attachmentCount }) : '';
        const statusTextParts = [resolveConversationInputStateLabel(entry.state), truncated, attachmentSuffixText].filter((part) => Boolean(part));
        const statusLabel = statusTextParts.join(' ');
        const removeButtonMarkup = isConversationInputRemovable(entry.state) ? uiHtml`<button type="button" class="remove-file-btn" data-action="chat:remove-conversation-input" data-input-id="${uiAttr(entry.inputId)}" aria-label="${uiAttr(removeLabel)}" data-tooltip="${uiAttr(removeLabel)}">${removeIcon}</button>` : uiHtml``;
        return buildChatFilePreviewItemDocumentMarkup({
            nameHtml,
            statusHtml: uiText(statusLabel),
            showSpinner: isConversationInputExecuting(entry.state),
            actionButtonMarkup: removeButtonMarkup
        });
    });

    const conversationInputsMarkup = joinUiHtml(rows);
    context.dependencies.updateHTML(inputQueuePreview, conversationInputsMarkup);
    setElementVisibility(context, 'inputQueuePreview', true);
}
