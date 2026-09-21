/* SoAI - Chat modal definitions registered by application bootstrap [frontend/assets/ts/features/chat/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { PageContext } from '@core/pagecontext/public.ts';
import { createModalElement, createModalElementFromMarkup } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';

import type { FirstRunStateStorage } from '@core/firstrun/protocols.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { WebuiUserEndpoints } from '@core/api/endpoints/webuiUserEndpoints.ts';
import { AGENT_PLAN_MODAL_ID, ARCHIVED_CONVERSATIONS_MODAL_ID, CHAT_ATTACHMENT_OVERFLOW_MODAL_ID, CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, CHAT_PROMPTS_PICKER_MODAL_ID, CHAT_TOOL_CALL_OUTPUT_MODAL_ID } from '@features/chat/modals/constants.ts';
import { createChatAttachModalDefinition } from '@features/chat/composerattachmodal/definition.ts';
import { CHARACTER_MAP_MODAL_DEFINITION } from '@features/chat/charactermap/definition.ts';
import { createChatMemoryProfileModalDefinition } from '@features/chat/modals/chatMemoryProfileModal.ts';
import { createVoiceCallModalDefinition } from '@features/chat/modals/voiceCallModal.ts';
import { renderArchivedConversationsModalScaffold } from '@features/chat/modals/archived/archivedConversationsModalScaffold.ts';
import { buildChatConfigurationModalMarkup } from '@features/chat/modals/markup/chatPageConfigurationModalMarkup.ts';
import { createChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';
import { buildChatMcpDefaultToolsModalMarkup } from '@features/chat/modals/markup/chatPageMcpDefaultToolsModalMarkup.ts';
import { MESSAGE_INFO_MODAL_ID } from '@features/chat/message/messageinfomodal/constants.ts';

const messageInfoModalDefinition: ModalDefinition = {
    id: MESSAGE_INFO_MODAL_ID,
    layout: 'md',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = MESSAGE_INFO_MODAL_ID;
        const titleId = modalUiId(modalId, 'title');
        const contentId = modalUiId(modalId, 'content');
        const copyButtonId = modalUiId(modalId, 'copy');
        const closeLabel = i18n.t('chat.message.infoModal.close');
        const copyLabel = i18n.t('common.copy');
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('chat.message.infoModal.title'),
            description: i18n.t('common.modalDescriptions.messageInfo'),
            closeLabel: i18n.t('common.close'),
            titleId
        });
        const body = renderModalBody('', { id: contentId, className: 'modal-body--sectioned' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
            right: renderModalFooterActionButton({ id: copyButtonId, text: copyLabel, variant: 'primary' })
        });
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'chat' },
            header,
            body,
            footer
        });
    }
};

const toolCallOutputModalDefinition: ModalDefinition = {
    id: CHAT_TOOL_CALL_OUTPUT_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = CHAT_TOOL_CALL_OUTPUT_MODAL_ID;
        const titleId = modalUiId(modalId, 'title');
        const contentId = modalUiId(modalId, 'content');
        const copyButtonId = modalUiId(modalId, 'copy');
        const closeLabel = i18n.t('common.close');
        const copyLabel = i18n.t('common.copy');
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('chat.toolCallOutputModal.title'),
            description: i18n.t('common.modalDescriptions.toolCallOutput'),
            closeLabel: i18n.t('common.close'),
            titleId
        });
        const body = renderModalBody('', { id: contentId, className: 'tool-call-output-modal-body' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
            right: renderModalFooterActionButton({ id: copyButtonId, text: copyLabel, variant: 'primary' })
        });
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'chat' },
            header,
            body,
            footer
        });
    }
};

const attachmentOverflowModalDefinition: ModalDefinition = {
    id: CHAT_ATTACHMENT_OVERFLOW_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = CHAT_ATTACHMENT_OVERFLOW_MODAL_ID;
        const titleId = modalUiId(modalId, 'title');
        const contentId = modalUiId(modalId, 'content');
        const closeLabel = i18n.t('common.close');
        const tabsId = modalUiId(modalId, 'tabs');
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('chat.attachments.modal.title'),
            description: i18n.t('common.modalDescriptions.chatAttachments'),
            closeLabel,
            titleId,
            sections: uiHtml`<div id="${tabsId}" class="chat-attachment-overflow-tabs-host"></div>`
        });
        const body = renderModalBody('', { id: contentId, className: 'modal-body--sectioned chat-attachment-overflow-modal-body' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel })
        });
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'chat' },
            header,
            body,
            footer
        });
    }
};

const renderChatPromptsPickerBody = (modalId: string): ReturnType<typeof uiHtml> => {
    const searchInputId = modalUiId(modalId, 'search');
    const searchButtonId = modalUiId(modalId, 'search-button');
    const resultsId = modalUiId(modalId, 'results');
    const statusId = modalUiId(modalId, 'status');
    const placeholder = uiAttr(i18n.t('prompts.searchPlaceholder'));
    const searchLabel = uiAttr(i18n.t('chat.promptsPicker.search'));
    return uiHtml`
        <div class="form-group setting-change-surface setting-change-surface--child-selection chat-prompts-picker-surface">
            <div class="chat-prompts-picker" data-chat-prompts-picker>
                <div class="form-row-split form-row-split--search ui-collection-search-row">
                    <div class="form-col-main ui-collection-search-row__field">
                        <div class="searchbar-container searchbar-container--collection">
                            <input type="text" id="${searchInputId}" class="form-input searchbar-input chat-prompts-picker-search-input" placeholder="${placeholder}" autocomplete="off">
                            ${renderSearchFieldActions()}
                        </div>
                    </div>
                    <div class="form-col-secondary form-col-action ui-collection-search-row__action">
                        <button class="ui-button" id="${searchButtonId}" type="button" aria-label="${searchLabel}" data-tooltip="${searchLabel}">${i18n.t('chat.promptsPicker.search')}</button>
                    </div>
                </div>
                <div class="form-help">${i18n.t('chat.promptsPicker.help')}</div>
                <div class="chat-prompts-picker-status" id="${statusId}" aria-live="polite"></div>
                <div class="chat-prompts-picker-results" id="${resultsId}"></div>
            </div>
        </div>
    `;
};

const chatPromptsPickerModalDefinition: ModalDefinition = {
    id: CHAT_PROMPTS_PICKER_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: modalUiSelector(CHAT_PROMPTS_PICKER_MODAL_ID, 'search'),
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = CHAT_PROMPTS_PICKER_MODAL_ID;
        const titleId = modalUiId(modalId, 'title');
        const manageButtonId = modalUiId(modalId, 'manage');
        const closeLabel = i18n.t('common.close');
        const manageLabel = i18n.t('chat.promptsPicker.manage');
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('chat.promptsPicker.title'),
            description: i18n.t('common.modalDescriptions.chatPromptsPicker'),
            closeLabel,
            titleId
        });
        const body = renderModalBody(renderChatPromptsPickerBody(modalId), { className: 'modal-body--sectioned chat-prompts-picker-modal-body' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
            right: renderModalFooterActionButton({ id: manageButtonId, text: manageLabel, variant: 'neutral' })
        });
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'chat' },
            header,
            body,
            footer
        });
    }
};

const createChatModalMarkupContext = () => {
    const pageContext = new PageContext({ pageId: 'chat' });
    return createChatPageMarkupContext(pageContext.sanitizer, windowIdentity.isDetachedContext());
};

const chatConfigurationModalDefinition: ModalDefinition = Object.freeze({
    id: CHAT_CONFIGURATION_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'user-name-input'),
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const markup = buildChatConfigurationModalMarkup(createChatModalMarkupContext());
        return createModalElementFromMarkup(CHAT_CONFIGURATION_MODAL_ID, markup);
    }
});

const chatMcpDefaultToolsModalDefinition: ModalDefinition = Object.freeze({
    id: CHAT_MCP_DEFAULT_TOOLS_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const markup = buildChatMcpDefaultToolsModalMarkup(createChatModalMarkupContext());
        return createModalElementFromMarkup(CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, markup);
    }
});

const agentPlanModalDefinition: ModalDefinition = {
    id: AGENT_PLAN_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = AGENT_PLAN_MODAL_ID;
        const titleId = modalUiId(modalId, 'title');
        const contentId = modalUiId(modalId, 'content');
        const copyButtonId = modalUiId(modalId, 'copy');
        const downloadButtonId = modalUiId(modalId, 'download');
        const closeLabel = i18n.t('common.close');
        const copyLabel = i18n.t('common.copy');
        const downloadLabel = i18n.t('common.download');
        const copyButton = renderModalFooterActionButton({ id: copyButtonId, text: copyLabel, variant: 'primary' });
        const downloadButton = renderModalFooterActionButton({ id: downloadButtonId, text: downloadLabel, variant: 'success' });
        const rightFooterActions = uiHtml`${copyButton}${downloadButton}`;
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('chat.agent.plan.modalTitle'),
            description: i18n.t('common.modalDescriptions.agentPlan'),
            closeLabel: i18n.t('common.close'),
            titleId
        });
        const body = renderModalBody('', { id: contentId, className: 'plan-view-modal-body' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
            right: rightFooterActions
        });
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'chat' },
            header,
            body,
            footer
        });
    }
};

const archivedConversationsModalDefinition: ModalDefinition = {
    id: ARCHIVED_CONVERSATIONS_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: '.archived-conversations-search-input',
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = ARCHIVED_CONVERSATIONS_MODAL_ID;
        const scaffold = renderArchivedConversationsModalScaffold();
        return createModalElement({
            id: modalId,
            rootAttributes: { 'data-page-scope': 'chat' },
            header: scaffold.header,
            body: scaffold.body,
            footer: scaffold.footer
        });
    }
};

const createChatModalDefinitions = (dependencies: { storage: FirstRunStateStorage; apiClient: ApiClientContext & { webui?: Pick<WebuiUserEndpoints, 'memory'> | undefined } }): readonly ModalDefinition[] => {
    return Object.freeze([messageInfoModalDefinition, toolCallOutputModalDefinition, createChatAttachModalDefinition(), attachmentOverflowModalDefinition, chatPromptsPickerModalDefinition, CHARACTER_MAP_MODAL_DEFINITION, chatConfigurationModalDefinition, chatMcpDefaultToolsModalDefinition, agentPlanModalDefinition, archivedConversationsModalDefinition, createChatMemoryProfileModalDefinition(dependencies), createVoiceCallModalDefinition()]);
};

export { createChatModalDefinitions };
