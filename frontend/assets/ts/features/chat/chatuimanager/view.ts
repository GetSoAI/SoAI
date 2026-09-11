/* SoAI - Chat UI manager view updates and input control rendering [frontend/assets/ts/features/chat/chatuimanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { CHAT_ICON_SIZE_MD, CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { resolveComposerControlState, type ChatComposerControlState } from '@features/chat/chatuimanager/composerControlState.ts';
import { getElement } from '@features/chat/chatuimanager/dom.ts';
import { updateAttachmentsPreview } from '@features/chat/chatuimanager/attachmentsPreview.ts';
import { resolveConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { isAgentModeRequiringTools } from '@features/chat/conversationsettings/mcpToolsActiveState.ts';
import { applyMcpToolsToggleButtonState } from '@features/chat/conversationsettings/mcpToolsToggleButtonState.ts';

const renderExecutionControls = (context: ChatUIManagerContext, controlState: ChatComposerControlState): void => {
    const nextIsExecuting = controlState.isExecuting;
    const nextIsChatStreaming = controlState.isChatStreaming;
    syncHeaderToolsToggleButton(context, nextIsExecuting);
    context.dependencies.composition.updateExportButtonVisibility();

    const actionBtn = getElement(context, 'actionBtn');
    if (!actionBtn) {
        return;
    }

    const messagesArea = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
    if (messagesArea instanceof HTMLElement) {
        context.dependencies.updateAttribute(messagesArea, 'data-chat-executing', nextIsExecuting ? 'true' : null);
    }
    const mode = nextIsExecuting && !nextIsChatStreaming && controlState.actionMode !== 'queue' ? 'send' : controlState.actionMode;
    context.dependencies.toggleClassName(actionBtn, 'is-stop-mode', mode === 'stop');
    actionBtn.setAttribute('data-chat-action-mode', mode);
    if (nextIsExecuting) {
        const hasConversation = context.dependencies.session.getCurrentConversationId() !== null;
        const disabled = mode === 'stop' || mode === 'steer' ? !nextIsChatStreaming || !hasConversation : mode === 'queue' ? !controlState.canQueue : true;
        context.dependencies.updateProperty(actionBtn, 'disabled', disabled);
    } else {
        context.dependencies.updateProperty(actionBtn, 'disabled', !controlState.canSend);
    }

    const iconName = mode === 'stop' ? 'stop' : 'arrow-up';
    context.dependencies.updateHTML(actionBtn, context.dependencies.getCachedIcon(iconName, CHAT_ICON_SIZE_MD));

    const label = mode === 'stop' ? i18n.t('chat.input.stop') : mode === 'steer' ? i18n.t('chat.input.steer') : mode === 'queue' ? i18n.t('chat.input.queue') : i18n.t('chat.input.send');
    setTooltipText(actionBtn, label);
    actionBtn.setAttribute('aria-label', label);
};

export function applyExecutionControls(context: ChatUIManagerContext): void {
    renderExecutionControls(context, resolveComposerControlState(context));
}

function syncHeaderToolsToggleButton(context: ChatUIManagerContext, isConversationExecuting: boolean): void {
    const toolsToggleButton = context.dependencies.optionalUI(CHAT_SELECTORS.TOOLS_TOGGLE_BTN);
    if (!(toolsToggleButton instanceof Element)) {
        return;
    }
    const conversation = context.dependencies.session.getCurrentConversation();
    const modelSettings = conversation?.modelSettings;
    const toolsEnabled = modelSettings?.mcp?.toolsEnabled === true;
    const modeRequiresTools = isAgentModeRequiringTools(modelSettings);
    applyMcpToolsToggleButtonState(toolsToggleButton, { toolsEnabled, modeRequiresTools, conversationExecuting: isConversationExecuting, authorityLock: resolveConversationAuthorityLock(conversation) });
}

function resolveSingleLineInputHeight(inputElement: HTMLTextAreaElement): number {
    const view = inputElement.ownerDocument.defaultView;
    if (!view) {
        return Math.max(inputElement.offsetHeight, 1);
    }
    const computed = view.getComputedStyle(inputElement);
    const lineHeight = Number.parseFloat(computed.lineHeight);
    const paddingTop = Number.parseFloat(computed.paddingTop);
    const paddingBottom = Number.parseFloat(computed.paddingBottom);
    const borderTop = Number.parseFloat(computed.borderTopWidth);
    const borderBottom = Number.parseFloat(computed.borderBottomWidth);
    const hasValidMetrics = Number.isFinite(lineHeight) && Number.isFinite(paddingTop) && Number.isFinite(paddingBottom) && Number.isFinite(borderTop) && Number.isFinite(borderBottom);
    if (!hasValidMetrics) {
        return Math.max(inputElement.offsetHeight, 1);
    }
    return Math.max(Math.ceil(lineHeight + paddingTop + paddingBottom + borderTop + borderBottom), 1);
}

export function updateInputState(context: ChatUIManagerContext): void {
    const input = getElement(context, 'input');
    if (!input) {
        return;
    }

    const inputElement = input instanceof HTMLTextAreaElement ? input : null;
    const controlState = resolveComposerControlState(context);
    const hasText = controlState.hasText;
    const inputWrapper = inputElement?.closest('.chat-input-wrapper');
    if (inputWrapper instanceof HTMLElement && inputElement instanceof HTMLTextAreaElement) {
        context.dependencies.toggleClassName(inputWrapper, 'chat-input-wrapper--has-text', hasText);
        if (inputElement.isConnected) {
            const singleLineHeightPx = resolveSingleLineInputHeight(inputElement);
            context.dependencies.dom.setStyle(inputWrapper, '--chat-input-empty-height', `${singleLineHeightPx}px`);

            const inputHeightPx = Math.max(inputElement.offsetHeight, singleLineHeightPx);
            const isSingleLine = inputHeightPx <= singleLineHeightPx + 2;
            const actionsHeightPx = isSingleLine ? inputHeightPx : singleLineHeightPx;
            context.dependencies.dom.setStyle(inputWrapper, '--chat-input-actions-height', `${actionsHeightPx}px`);
        }
    }

    const actionBtn = getElement(context, 'actionBtn');
    if (!actionBtn) {
        return;
    }

    renderExecutionControls(context, controlState);
}

export { updateAttachmentsPreview };
