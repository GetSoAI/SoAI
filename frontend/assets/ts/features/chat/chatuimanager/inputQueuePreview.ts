/* SoAI - Chat feature input queue preview [frontend/assets/ts/features/chat/chatuimanager/inputQueuePreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationInputActiveState } from '@core/chat/protocols.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { getElement, setElementVisibility } from '@features/chat/chatuimanager/dom.ts';
import { buildChatFilePreviewItemDocumentMarkup } from '@features/chat/chatuimanager/filePreviewItemDocumentMarkup.ts';
import { dom } from '@core/dom/dom.ts';
import { reconcileAttachmentPreview } from '@features/chat/chatuimanager/attachmentPreviewReconciler.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import type { ConversationInputPreview, ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

type ConversationInputPreviewState = ConversationInputActiveState | 'regeneration_failed';

const resolveConversationInputStateLabel = (state: ConversationInputPreviewState): string => {
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

export const isConversationInputRemovable = (state: ConversationInputPreviewState): boolean => state === 'pending' || state === 'materializing';

const isConversationInputExecuting = (state: ConversationInputPreviewState): boolean => state === 'materializing' || state === 'running';

export function resolveQueuedConversationInputs(context: ChatUIManagerContext): ConversationInputPreview[] {
    const conversationInputs = context.dependencies.drafts.getConversationInputs();
    return isArray(conversationInputs)
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
}

export function updateInputQueuePreview(context: ChatUIManagerContext, validPrompts: readonly ConversationInputPreview[] = resolveQueuedConversationInputs(context)): void {
    const inputQueuePreview = getElement(context, 'inputQueuePreview');
    if (!inputQueuePreview) return;
    const conversationId = context.dependencies.session.getCurrentConversationId();

    if (validPrompts.length === 0) {
        reconcileAttachmentPreview(context, inputQueuePreview, []);
        setElementVisibility(context, 'inputQueuePreview', false);
        return;
    }

    const removeLabel = i18n.t('chat.attachments.removeTooltip');
    const removeIcon = context.dependencies.getCachedIcon('close', { size: 12, strokeWidth: 2.2 });
    const retryLabel = i18n.t('pageOutlet.retry');
    const retryIcon = context.dependencies.getCachedIcon('refresh', { size: 12, strokeWidth: 2.2 });

    const rows = validPrompts.map((entry) => {
        const inputType = entry.inputType === 'steer' ? 'steer' : 'prompt';
        const isRegenerationRetry = entry.state === 'regeneration_failed';
        const badgeText = isRegenerationRetry ? i18n.t('chat.message.actions.regenerate') : inputType === 'steer' ? i18n.t('chat.inputQueue.badge.steer') : entry.isHeld ? i18n.t('chat.inputQueue.badge.held') : i18n.t('chat.inputQueue.badge.queued');
        const badgeClass = isRegenerationRetry ? 'input-queue-badge' : inputType === 'steer' ? 'input-queue-badge input-queue-badge--steer' : entry.isHeld ? 'input-queue-badge input-queue-badge--held' : 'input-queue-badge input-queue-badge--queued';

        const conversationInputLabel = i18n.t('chat.attachments.conversationInputQueue');
        const normalized = isString(entry.text) ? entry.text.replace(/\s+/g, ' ').trim() : '';
        const attachmentCount = isArray(entry.attachmentContent) ? entry.attachmentContent.length : 0;
        const attachmentCountLabel = attachmentCount > 0 ? i18n.t('chat.inputQueue.attachmentsCount', { count: attachmentCount }) : '';
        const attachmentChip = attachmentCount > 0 ? uiHtml`<span class="input-queue-attachment-count" aria-label="${uiAttr(attachmentCountLabel)}"><span aria-hidden="true">${context.dependencies.getCachedIcon('paperclip', { size: 12, strokeWidth: 2.2 })}</span><span aria-hidden="true">${uiText(String(attachmentCount))}</span></span>` : uiHtml``;
        const nameHtml = uiHtml`<span class="input-queue-prompt-title">${uiText(conversationInputLabel)}</span>${attachmentChip}<span class="${uiAttr(badgeClass)}">${uiText(badgeText)}</span>`;
        const statusTextParts = [resolveConversationInputStateLabel(entry.state), normalized].filter((part) => Boolean(part));
        const statusLabel = statusTextParts.join(' ');
        const removeButtonMarkup = isConversationInputRemovable(entry.state) ? uiHtml`<button type="button" class="remove-file-btn" data-action="${uiAttr(CHAT_ACTIONS.REMOVE_CONVERSATION_INPUT)}" data-conversation-id="${uiAttr(conversationId ?? '')}" data-input-id="${uiAttr(entry.inputId)}" aria-label="${uiAttr(removeLabel)}" data-tooltip="${uiAttr(removeLabel)}">${removeIcon}</button>` : uiHtml``;
        const retryButtonMarkup = isRegenerationRetry ? uiHtml`<button type="button" class="remove-file-btn" data-action="${uiAttr(CHAT_ACTIONS.RETRY_CONVERSATION_REGENERATION)}" data-input-id="${uiAttr(entry.inputId)}" aria-label="${uiAttr(retryLabel)}" data-tooltip="${uiAttr(retryLabel)}">${retryIcon}</button>` : uiHtml``;
        const interactiveBodyAttributesMarkup = !isRegenerationRetry && conversationId !== null ? uiHtml` data-action="${uiAttr(CHAT_ACTIONS.OPEN_CONVERSATION_INPUT)}" data-conversation-id="${uiAttr(conversationId)}" data-input-id="${uiAttr(entry.inputId)}"` : undefined;
        const promptLabel = [badgeText, normalized, attachmentCountLabel].filter(Boolean).join(' ');
        return {
            id: `${conversationId ?? ''}:${entry.inputId}`,
            html: buildChatFilePreviewItemDocumentMarkup({
                interactiveBodyAttributesMarkup,
                interactiveBodyLabel: i18n.t('chat.inputQueue.open', { prompt: promptLabel }),
                nameHtml,
                statusHtml: uiText(statusLabel),
                showSpinner: isConversationInputExecuting(entry.state),
                actionButtonMarkup: isRegenerationRetry ? retryButtonMarkup : removeButtonMarkup
            })
        };
    });

    const focused = dom.getActiveElement();
    const focusedInputId = focused instanceof HTMLElement && inputQueuePreview.contains(focused) ? dom.getData(focused, 'inputId') : null;
    const focusedAction = focusedInputId !== null ? dom.getData(focused, 'action') : null;
    reconcileAttachmentPreview(context, inputQueuePreview, rows);
    if (focusedInputId !== null && focused instanceof HTMLElement && !focused.isConnected) {
        const candidates = dom.resolveAll('[data-input-id]', inputQueuePreview).filter((element) => dom.getData(element, 'inputId') === focusedInputId);
        const target = candidates.find((element) => dom.getData(element, 'action') === focusedAction) ?? candidates.find((element) => dom.getData(element, 'action') === CHAT_ACTIONS.OPEN_CONVERSATION_INPUT);
        if (target instanceof HTMLElement) target.focus({ preventScroll: true });
    }
    setElementVisibility(context, 'inputQueuePreview', true);
}
