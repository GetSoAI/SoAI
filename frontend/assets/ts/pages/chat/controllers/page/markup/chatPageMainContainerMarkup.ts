/* SoAI - Chat page main container markup [frontend/assets/ts/pages/chat/controllers/page/markup/chatPageMainContainerMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { CONVERSATION_TITLE_MAX_LENGTH, type ChatPageMarkupContext } from '@features/chat/public.ts';
import { renderChatHeaderOverflowComposerButtons, renderChatInputActionButtonsInline } from '@pages/chat/controllers/page/markup/ChatInputActionButtonsWidget.ts';

const buildChatMainContainerMarkup = (context: ChatPageMarkupContext): string => {
    const { strings, sanitizer } = context;
    const sidebarToggleButton = `<button type="button" class="chat-sidebar-toggle-btn ui-icon-button" data-action="chat:toggle-sidebar" ${renderLabelAttributes(strings.toggleSidebar)}></button>`;
    const editLabel = i18n.attr(sanitizer, 'common.edit');
    const agentCompactTooltip = i18n.t('chat.agent.compact.tooltip');
    const planBarToggleTooltip = i18n.t('chat.header.togglePlanBar');
    const newTitleAttr = i18n.attr(sanitizer, 'chat.conversation.newTitle');
    const inputActionsInlineHtml = renderChatInputActionButtonsInline(context);
    const headerOverflowComposerButtonsHtml = renderChatHeaderOverflowComposerButtons(context);

    return `<div class="chat-main-container glass-surface-strong glass-surface--rounded">
        <div class="chat-conversation-header glass-surface--no-shadow">
        <div class="chat-header-left">
	        ${sidebarToggleButton}
	        <div class="conversation-title-wrapper ui-inline-text-edit">
	        <button type="button" class="conversation-title ui-inline-text-edit__trigger" data-action="chat:start-conversation-title-edit" ${renderLabelAttributes(i18n.t('common.edit'))}><span class="conversation-title-text ui-inline-text-edit__text">${strings.newTitle}</span><span class="conversation-title-automation-indicator u-hidden" aria-hidden="true"></span><span class="conversation-title-messaging-indicator u-hidden" aria-hidden="true"></span><span class="conversation-title-archive-indicator u-hidden" aria-hidden="true"></span></button>
	        <input type="text" class="conversation-title-input ui-inline-text-edit__input u-hidden" aria-label="${editLabel}" value="${newTitleAttr}" maxlength="${CONVERSATION_TITLE_MAX_LENGTH}">
	        <button type="button" class="conversation-title-save-btn ui-inline-text-edit__save ui-button ui-variant-accent u-hidden" data-action="chat:conversation-title-save" ${renderLabelAttributes(strings.titleSave)}>${strings.saveCommon}</button>
	        <button type="button" class="conversation-title-cancel-btn ui-inline-text-edit__cancel ui-button ui-variant-neutral u-hidden" data-action="chat:conversation-title-cancel" ${renderLabelAttributes(strings.titleCancel)}>${strings.cancelCommon}</button>
	        </div>
        </div>
        <div class="chat-header-actions">
        <div class="chat-header-overflow page-actions">
        <button type="button" class="chat-overflow-trigger ui-icon-button page-actions__trigger" ${renderLabelAttributes(strings.moreActions)} aria-haspopup="true" aria-expanded="false"><span class="chat-action-icon" aria-hidden="true"></span></button>
        <div class="page-actions__menu page-actions__menu--split" role="toolbar">
        <button type="button" class="agent-mode-cycle-btn ui-button" data-action="chat:cycle-agent-mode" data-agent-mode="chat" data-page-actions-menu-keep-open="true" ${renderLabelAttributes(strings.agentModeCycleTooltip)}><span class="agent-mode-cycle-icon ui-icon" aria-hidden="true"></span><span class="agent-mode-cycle-label">${strings.agentModeChat}</span></button>
        <button type="button" class="agent-compact-btn chat-header-action ui-button u-hidden" data-action="chat:compact-agent" ${renderLabelAttributes(agentCompactTooltip)}><span class="ui-icon chat-action-icon" aria-hidden="true"></span><span class="chat-action-label">${strings.agentCompact}</span></button>
        <button type="button" class="export-btn chat-header-action ui-button u-hidden" data-action="chat:export-conversation" ${renderLabelAttributes(strings.exportAction)}><span class="ui-icon chat-action-icon" aria-hidden="true"></span><span class="chat-action-label">${strings.exportAction}</span></button>
        <button type="button" class="configuration-toggle-btn configuration-toggle-btn--dropdown chat-header-action ui-button" data-action="chat:toggle-configuration" ${renderLabelAttributes(strings.configuration)}><span class="ui-icon chat-action-icon" aria-hidden="true"></span><span class="chat-action-label">${strings.configuration}</span></button>
        ${headerOverflowComposerButtonsHtml}
        </div>
        </div>
        <button type="button" class="header-favorite-btn chat-header-action ui-button" data-action="chat:toggle-current-favorite" data-page-actions-menu-keep-open="true" ${renderLabelAttributes(strings.toggleFavorite)} aria-pressed="false"><span class="ui-icon chat-action-icon" aria-hidden="true"></span><span class="chat-action-label">${strings.toggleFavorite}</span></button>
        <button type="button" class="tools-toggle-btn chat-header-action ui-button" data-action="chat:toggle-tools" data-page-actions-menu-keep-open="true" ${renderLabelAttributes(strings.toggleTools)} aria-pressed="false"><span class="ui-icon chat-action-icon" aria-hidden="true"></span><span class="chat-action-label">${strings.toggleTools}</span></button>
        <button type="button" class="plan-bar-toggle-btn chat-header-action ui-button ui-variant-violet u-hidden" data-action="chat:toggle-plan-bar" data-page-actions-menu-keep-open="true" aria-controls="agent-todo-panel-container" aria-expanded="true" ${renderLabelAttributes(planBarToggleTooltip)}><span class="ui-icon chat-action-icon" aria-hidden="true"></span><span class="chat-action-label"></span></button>
        <button type="button" class="configuration-toggle-btn ui-icon-button" data-action="chat:toggle-configuration" ${renderLabelAttributes(strings.configuration)}></button>
        </div>
        </div>
        <div class="chat-plan-messages-region">
        <div class="agent-todo-panel-container" id="agent-todo-panel-container" data-agent-todo-panel-visibility="hidden" inert></div>
        <div class="chat-messages-area-shell">
        <div class="chat-messages-area"><div class="chat-messages" id="chat-messages"></div></div>
        <div class="chat-advanced-scroll chat-advanced-scroll--hidden" aria-hidden="true">
        <div class="chat-advanced-scroll-canvas" aria-hidden="true"></div>
        <div class="chat-advanced-scroll-fade chat-advanced-scroll-fade--top" aria-hidden="true"></div>
        <div class="chat-advanced-scroll-fade chat-advanced-scroll-fade--bottom" aria-hidden="true"></div>
        <div class="chat-advanced-scroll-viewport" aria-hidden="true"></div>
        </div>
        </div>
        </div>
        <div class="chat-previews-container u-hidden" id="chat-previews-container">
        <div class="input-queue-preview glass-surface-strong u-hidden" aria-hidden="true"></div>
        <div class="tool-approval-preview glass-surface-strong u-hidden" aria-hidden="true"></div>
        <div class="ask-user-preview glass-surface-strong u-hidden" aria-hidden="true"></div>
        <div class="secret-prompt-preview glass-surface-strong u-hidden" aria-hidden="true"></div>
        <div class="voice-recording-preview glass-surface-strong u-hidden" aria-hidden="true"></div>
        <div class="attached-files-preview glass-surface-strong u-hidden" aria-hidden="true"></div>
        </div>
        <div class="chat-input-area">
        <div class="input-container">
        <input type="file" class="file-upload-input u-hidden" multiple>
        <input type="file" class="folder-upload-input u-hidden" webkitdirectory directory multiple>
        <input type="file" class="u-hidden user-avatar-file-input" accept="image/*">
        <input type="file" class="u-hidden assistant-avatar-file-input" accept="image/*">
	        <div class="chat-input-wrapper glass-surface-strong">
			        <textarea class="chat-input" aria-label="${strings.inputPlaceholder}" placeholder="${strings.inputPlaceholder}" rows="1"></textarea>
			        <div class="chat-input-actions chat-input-actions--hydrating">
                ${inputActionsInlineHtml.leading}
                <div class="model-selector model-selector--composer page-header-filter-select" data-chat-model-control="true" data-scope="composer" aria-label="${strings.selectModel}"></div>
			        <div class="chat-composer-skeleton-actions" aria-hidden="true">
			        <span class="chat-composer-skeleton-button"></span>
			        <span class="chat-composer-skeleton-button"></span>
			        </div>
			        <div class="chat-input-actions-inline">
			        ${inputActionsInlineHtml.auxiliary}
			        </div>
			        <div class="chat-mobile-auxiliary-action-slot u-hidden" data-mobile-auxiliary-action="none"></div>
		        <button type="button" class="chat-action-btn square-btn" data-action="chat:send-or-stop" ${renderLabelAttributes(strings.send)} disabled></button>
		        </div>
	        </div>
        </div>
        </div>
        </div>
        </div>`;
};

export { buildChatMainContainerMarkup };
