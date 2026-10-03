/* SoAI - Queued conversation input detail sessions [frontend/assets/ts/features/chat/chatuimanager/conversationInputModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { createElementResolver } from '@core/dom/elementResolver.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import { syncTextContent } from '@core/dom/patching.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import { getBusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { toggleHidden } from '@core/ui/visibility.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { prepareAttachmentThumbnailLifecycles } from '@features/chat/attachments/chatImageLoadLifecycle.ts';
import { reconcileAttachmentPreview, type AttachmentPreviewEntry } from '@features/chat/chatuimanager/attachmentPreviewReconciler.ts';
import { getElement } from '@features/chat/chatuimanager/dom.ts';
import { isConversationInputRemovable, resolveQueuedConversationInputs } from '@features/chat/chatuimanager/inputQueuePreview.ts';
import type { ChatUIManagerContext, ConversationInputModalSession, ConversationInputPreview } from '@features/chat/chatuimanager/types.ts';
import { buildMessageContentSegments } from '@features/chat/message/messageSegmentsFromContent.ts';
import { isAttachmentSummarySegment, renderAttachmentCard, renderAttachmentStrip } from '@features/chat/message/messageview/attachmentSummaryCards.ts';
import { createChatAttachmentCardRenderHost } from '@features/chat/message/messageview/renderHost.ts';
import { CHAT_CONVERSATION_INPUT_MODAL_ID } from '@features/chat/modals/constants.ts';

const buildConversationInputCards = (context: ChatUIManagerContext, entry: ConversationInputPreview, conversationId: string): AttachmentPreviewEntry[] => {
    const segments = buildMessageContentSegments([...entry.attachmentContent]);
    const attachments = segments.filter(isAttachmentSummarySegment);
    if (attachments.length !== entry.attachmentContent.length || attachments.length !== segments.length) {
        throw new Error('Conversation input attachments must all have summary cards');
    }
    const host = createChatAttachmentCardRenderHost({ sanitizer: context.dependencies.sanitizer, getIcon: context.dependencies.getCachedIcon });
    return attachments.map((segment, index) => {
        const identity = segment.type === 'soai_file' ? [segment.attachmentId, segment.fileId, segment.attachmentRevision] : segment.type === 'soai_knowledge' ? [segment.knowledgeAttachmentId, segment.sourceType] : segment.type === 'soai_path' ? segment.contentPart : segment.type === 'image' ? segment.imageUrl : null;
        return { id: stableJsonStringify([entry.inputId, index, segment.type, identity]), html: toTrustedUiHtml(renderAttachmentCard(host, segment, { conversationId })) };
    });
};

const updateConversationInputModalContent = (context: ChatUIManagerContext, session: ConversationInputModalSession, entry: ConversationInputPreview, cards: readonly AttachmentPreviewEntry[]): void => {
    const resolver = createElementResolver(session.modal, 'Conversation input modal');
    syncTextContent(resolver.requireHTMLElement(modalUiSelector(CHAT_CONVERSATION_INPUT_MODAL_ID, 'title')), i18n.t('chat.attachments.conversationInputQueue'));
    syncTextContent(resolver.requireHTMLElement(modalUiSelector(CHAT_CONVERSATION_INPUT_MODAL_ID, 'description')), i18n.t('common.modalDescriptions.conversationInput'));
    const headerClose = narrowButton(resolver.requireHTMLElement(MODAL_HEADER_CLOSE_SELECTOR), 'Conversation input header close');
    const footerClose = narrowButton(resolver.requireHTMLElement(modalUiSelector(CHAT_CONVERSATION_INPUT_MODAL_ID, 'close')), 'Conversation input footer close');
    for (const button of [headerClose, footerClose, session.deleteButton]) {
        if (getBusyDisabledToken(button) !== null) continue;
        const label = button === session.deleteButton ? i18n.t('common.delete') : i18n.t('common.close');
        if (button !== headerClose) syncTextContent(button, label);
        dom.setAttribute(button, 'aria-label', label);
        setTooltipText(button, label);
    }
    syncTextContent(session.textElement, entry.text);
    toggleHidden(session.textElement, entry.text.length === 0);
    const result = reconcileAttachmentPreview(context, session.attachmentStrip, cards);
    toggleHidden(session.attachmentStrip, cards.length === 0);
    dom.setData(session.attachmentStrip, 'attachmentCount', String(cards.length));
    if (result.thumbnailsChanged) prepareAttachmentThumbnailLifecycles(session.attachmentStrip);
    if (getBusyDisabledToken(session.deleteButton) === null) setControlDisabledState(session.deleteButton, !isConversationInputRemovable(entry.state));
};

const closeConversationInputModal = (context: ChatUIManagerContext, reason: string, restoreComposerFocus: boolean): void => {
    const session = context.state.conversationInputModal;
    if (session === null) return;
    const input = restoreComposerFocus ? getElement(context, 'input') : null;
    const focused = dom.getActiveElement();
    const hadFocus = focused !== null && session.modal.contains(focused);
    session.presenter.close(CHAT_CONVERSATION_INPUT_MODAL_ID, { reason, force: true, restoreFocus: false, replacementFocusTarget: input ?? undefined });
    if (hadFocus && input?.isConnected) input.focus({ preventScroll: true });
};

const syncConversationInputModal = (context: ChatUIManagerContext, entries: readonly ConversationInputPreview[]): void => {
    const session = context.state.conversationInputModal;
    if (session === null) return;
    const entry = session.conversationId === context.dependencies.session.getCurrentConversationId() ? entries.find((candidate) => candidate.inputId === session.inputId && candidate.state !== 'regeneration_failed') : undefined;
    if (entry === undefined) {
        closeConversationInputModal(context, 'input-unavailable', true);
        return;
    }
    try {
        const cards = buildConversationInputCards(context, entry, session.conversationId);
        updateConversationInputModalContent(context, session, entry, cards);
    } catch (error) {
        closeConversationInputModal(context, 'invalid-input-content', true);
        throw ensureError(error);
    }
};

const openConversationInputModal = async (context: ChatUIManagerContext, resolvePresenter: () => ModalPresenterApi, conversationId: string, inputId: string): Promise<void> => {
    if (conversationId !== context.dependencies.session.getCurrentConversationId()) return;
    const entry = resolveQueuedConversationInputs(context).find((candidate) => candidate.inputId === inputId && candidate.state !== 'regeneration_failed');
    if (entry === undefined) return;
    const current = context.state.conversationInputModal;
    if (current?.conversationId === conversationId && current.inputId === inputId) return;
    const cards = buildConversationInputCards(context, entry, conversationId);
    const presenter = resolvePresenter();
    await runModalSession({
        presenter,
        modalId: CHAT_CONVERSATION_INPUT_MODAL_ID,
        initialResult: undefined,
        initialize: ({ modal }) => {
            const resolver = createElementResolver(modal, 'Conversation input modal');
            const body = resolver.requireHTMLElement(modalUiSelector(CHAT_CONVERSATION_INPUT_MODAL_ID, 'content'));
            const textElement = resolver.requireHTMLElement(modalUiSelector(CHAT_CONVERSATION_INPUT_MODAL_ID, 'text'));
            const attachments = resolver.requireHTMLElement(modalUiSelector(CHAT_CONVERSATION_INPUT_MODAL_ID, 'attachments'));
            const deleteButton = narrowButton(resolver.requireHTMLElement(modalUiSelector(CHAT_CONVERSATION_INPUT_MODAL_ID, 'delete')), 'Conversation input delete');
            const host = createChatAttachmentCardRenderHost({ sanitizer: context.dependencies.sanitizer, getIcon: context.dependencies.getCachedIcon });
            context.dependencies.updateHTML(attachments, toTrustedUiHtml(renderAttachmentStrip(host, [], { conversationId })));
            const attachmentStrip = resolver.requireHTMLElement('.message-attachment-strip', attachments);
            const session: ConversationInputModalSession = { conversationId, inputId, modal, body, textElement, attachmentStrip, deleteButton, presenter };
            context.state.conversationInputModal = session;
            const dispose = (): void => {
                if (context.state.conversationInputModal !== session) return;
                context.state.conversationInputModal = null;
                clearLoadingButtonIfNeeded(deleteButton);
                setControlDisabledState(deleteButton, true);
                syncTextContent(textElement, '');
                context.dependencies.updateHTML(attachments, '');
                dom.setData(modal, 'conversationId', null);
                dom.setData(deleteButton, 'conversationId', null);
                dom.setData(deleteButton, 'inputId', null);
            };
            try {
                updateConversationInputModalContent(context, session, entry, cards);
                dom.setData(modal, 'conversationId', conversationId);
                dom.setData(deleteButton, 'conversationId', conversationId);
                dom.setData(deleteButton, 'inputId', inputId);
            } catch (error) {
                dispose();
                throw ensureError(error);
            }
            return { dispose };
        }
    });
};

export { closeConversationInputModal, openConversationInputModal, syncConversationInputModal };
