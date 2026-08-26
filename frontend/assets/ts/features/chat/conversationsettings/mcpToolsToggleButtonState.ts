/* SoAI - Chat feature MCP tools toggle button state [frontend/assets/ts/features/chat/conversationsettings/mcpToolsToggleButtonState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { applyAuthorityLockedButtonState, type ConversationAuthorityLock } from '@core/chat/conversationAuthorityLock.ts';
import { getBusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';

interface McpToolsToggleButtonState {
    toolsEnabled: boolean;
    modeRequiresTools: boolean;
    conversationExecuting: boolean;
    authorityLock: ConversationAuthorityLock | null;
}

const resolveAriaLabel = (state: McpToolsToggleButtonState): string => {
    if (state.modeRequiresTools) {
        return i18n.t('chat.agent.tools.requiredForMode');
    }
    if (state.conversationExecuting) {
        return i18n.t('chat.agent.tools.lockedWhileConversationRunning');
    }
    return i18n.t('chat.header.toggleTools');
};

const applyMcpToolsToggleButtonState = (button: Element, state: McpToolsToggleButtonState): void => {
    if (!(button instanceof HTMLButtonElement)) {
        throw new TypeError('Chat tools toggle control must be a button');
    }
    const active = state.toolsEnabled || state.modeRequiresTools;
    const unlockedDisabled = state.modeRequiresTools || state.conversationExecuting;
    const toggleToolsLabel = i18n.t('chat.header.toggleTools');
    button.classList.toggle('is-tools-active', active);
    button.dataset['toolsModeLocked'] = state.modeRequiresTools ? 'true' : 'false';
    button.dataset['toolsExecutionLocked'] = state.conversationExecuting ? 'true' : 'false';
    button.setAttribute('aria-pressed', active ? 'true' : 'false');
    if (getBusyDisabledToken(button) !== null) {
        return;
    }
    applyAuthorityLockedButtonState(button, {
        lock: state.authorityLock,
        actionLabel: toggleToolsLabel,
        unlockedAriaLabel: resolveAriaLabel(state),
        unlockedTooltip: unlockedDisabled ? '' : toggleToolsLabel,
        unlockedDisabled
    });
};

export { applyMcpToolsToggleButtonState };
