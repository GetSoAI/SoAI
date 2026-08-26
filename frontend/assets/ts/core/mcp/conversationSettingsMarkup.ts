/* SoAI - Shared MCP conversation settings markup [frontend/assets/ts/core/mcp/conversationSettingsMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeModalId } from '@core/modals/guards.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';

interface McpConversationSettingsMarkupStrings {
    serversEmpty: string;
    toolsEmpty: string;
    enabledLabelAttr: string;
    disabledLabelAttr: string;
    disabledLabel: string;
}

interface McpConversationDefaultToolsMarkup {
    modalId: string;
    title: string;
    open: string;
    summary: string;
    summaryHint: string;
    openTitleAttr: string;
    triggerAction?: string | undefined;
}

interface McpConversationResetToolsMarkup {
    title: string;
    description: string;
    label: string;
    action?: string | undefined;
}

interface McpConversationToggleMarkup {
    label: string;
    hint: string;
    action?: string | undefined;
}

interface McpDefaultToolsModalBodyStrings {
    toolsTitle: string;
    toolsEmpty: string;
}

const buildMcpConversationSettingsBodyMarkup = (inputArguments: { modalId: string; strings: McpConversationSettingsMarkupStrings; toolsEnabledToggle?: McpConversationToggleMarkup | undefined; toolApprovalRequiredToggle?: McpConversationToggleMarkup | undefined; defaultTools?: McpConversationDefaultToolsMarkup | undefined; resetTools?: McpConversationResetToolsMarkup | undefined; disableInteractions?: boolean | undefined; includeServersList?: boolean | undefined }): string => {
    const modalId = normalizeModalId(inputArguments.modalId);
    const toolsEnabledToggleId = modalUiId(modalId, 'mcp-tools-enabled-toggle');
    const toolApprovalRequiredToggleId = modalUiId(modalId, 'mcp-tool-approval-required-toggle');
    const serversListId = modalUiId(modalId, 'mcp-servers-list');
    const serversEmptyId = modalUiId(modalId, 'mcp-servers-empty');
    const toolsListId = modalUiId(modalId, 'mcp-tools-list');
    const toolsEmptyId = modalUiId(modalId, 'mcp-tools-empty');
    const disabledAttr = inputArguments.disableInteractions ? ' disabled' : '';

    const strings = inputArguments.strings;
    const toolsEnabledToggle = inputArguments.toolsEnabledToggle;
    const toolApprovalRequiredToggle = inputArguments.toolApprovalRequiredToggle;
    const toolsEnabledToggleActionAttr = toolsEnabledToggle?.action ? ` data-action="${uiAttr(toolsEnabledToggle.action).html}"` : '';
    const toolApprovalRequiredToggleActionAttr = toolApprovalRequiredToggle?.action ? ` data-action="${uiAttr(toolApprovalRequiredToggle.action).html}"` : '';
    const defaultTools = inputArguments.defaultTools;
    const defaultToolsSummaryId = modalUiId(modalId, 'mcp-default-tools-summary');
    const defaultToolsTriggerActionAttr = defaultTools?.triggerAction ? ` data-action="${uiAttr(defaultTools.triggerAction).html}"` : '';
    const defaultToolsMarkup = defaultTools ? `<button type="button" class="chat-configuration-section-header mcp-default-tools-trigger setting-change-surface" aria-haspopup="dialog" aria-controls="${normalizeModalId(defaultTools.modalId)}" aria-expanded="false" aria-label="${defaultTools.openTitleAttr}" data-tooltip="${defaultTools.openTitleAttr}"${defaultToolsTriggerActionAttr}${disabledAttr}>` + `<span class="mcp-default-tools-title">${defaultTools.title}</span>` + `<span class="ui-button mcp-default-tools-open-btn" aria-hidden="true">${defaultTools.open}</span>` + `</button>` + `<div id="${defaultToolsSummaryId}" class="chat-configuration-hint mcp-default-tools-summary">${defaultTools.summary}</div>` + `<div class="chat-configuration-hint mcp-default-tools-summary-hint">${defaultTools.summaryHint}</div>` : '';
    const resetTools = inputArguments.resetTools;
    const resetToolsActionAttr = resetTools?.action ? ` data-action="${uiAttr(resetTools.action).html}"` : '';
    const resetDescription = resetTools?.description ?? '';
    const resetToolsMarkup = resetTools ? `<div class="chat-configuration-section-header mcp-tool-reset-row">` + `<span class="chat-configuration-section-title">${uiText(resetTools.title).html}</span>` + `<button type="button" class="ui-button ui-variant-danger mcp-tool-mode-reset-btn" aria-label="${uiAttr(resetDescription).html}" data-tooltip="${uiAttr(resetDescription).html}"${resetToolsActionAttr}${disabledAttr}>${uiText(resetTools.label).html}</button>` + `<span class="chat-configuration-hint mcp-tool-mode-reset-description">${uiText(resetDescription).html}</span>` + `</div>` : '';
    const serversListMarkup = inputArguments.includeServersList === false ? '' : `<div id="${serversListId}" class="mcp-servers-list"></div>` + `<div id="${serversEmptyId}" class="mcp-servers-empty u-hidden">${strings.serversEmpty}</div>`;
    return (
        `<div class="mcp-tools-scope">` +
        (toolsEnabledToggle ? `<div class="form-group setting-change-surface">` + `<label for="${toolsEnabledToggleId}">${toolsEnabledToggle.label}</label>` + `<div class="toggle-switch">` + `<input type="checkbox" id="${toolsEnabledToggleId}" class="mcp-tools-enabled-toggle mcp-input" data-toggle-label-true="${strings.enabledLabelAttr}" data-toggle-label-false="${strings.disabledLabelAttr}"${toolsEnabledToggleActionAttr}${disabledAttr}>` + `<label class="slider" for="${toolsEnabledToggleId}"></label>` + `<span class="toggle-label">${strings.disabledLabel}</span>` + `</div>` + `<span class="chat-configuration-hint mcp-tools-enabled-hint">${toolsEnabledToggle.hint}</span>` + `</div>` : '') +
        (toolApprovalRequiredToggle ? `<div class="form-group setting-change-surface">` + `<label for="${toolApprovalRequiredToggleId}">${toolApprovalRequiredToggle.label}</label>` + `<div class="toggle-switch">` + `<input type="checkbox" id="${toolApprovalRequiredToggleId}" class="mcp-tool-approval-required-toggle mcp-input" data-toggle-label-true="${strings.enabledLabelAttr}" data-toggle-label-false="${strings.disabledLabelAttr}"${toolApprovalRequiredToggleActionAttr}${disabledAttr}>` + `<label class="slider" for="${toolApprovalRequiredToggleId}"></label>` + `<span class="toggle-label">${strings.disabledLabel}</span>` + `</div>` + `<span class="chat-configuration-hint mcp-tool-approval-required-hint">${toolApprovalRequiredToggle.hint}</span>` + `</div>` : '') +
        serversListMarkup +
        `<div id="${toolsListId}" class="mcp-tools-list"></div>` +
        `<div id="${toolsEmptyId}" class="mcp-tools-empty u-hidden">${strings.toolsEmpty}</div>` +
        defaultToolsMarkup +
        resetToolsMarkup +
        `</div>`
    );
};

const buildMcpDefaultToolsModalBodyMarkup = (inputArguments: { modalId: string; strings: McpDefaultToolsModalBodyStrings; resetTools?: McpConversationResetToolsMarkup | undefined }): string => {
    const modalId = normalizeModalId(inputArguments.modalId);
    const listId = modalUiId(modalId, 'mcp-default-tools-list');
    const emptyId = modalUiId(modalId, 'mcp-default-tools-empty');
    const resetTools = inputArguments.resetTools;
    const resetToolsActionAttr = resetTools?.action ? ` data-action="${uiAttr(resetTools.action).html}"` : '';
    const resetDescription = resetTools?.description ?? '';
    const resetToolsMarkup = resetTools ? `<div class="chat-configuration-section-header mcp-tool-reset-row mcp-tool-reset-row--modal">` + `<span class="chat-configuration-section-title">${uiText(resetTools.title).html}</span>` + `<button type="button" class="ui-button ui-variant-danger mcp-tool-mode-reset-btn" aria-label="${uiAttr(resetDescription).html}" data-tooltip="${uiAttr(resetDescription).html}"${resetToolsActionAttr}>${uiText(resetTools.label).html}</button>` + `<span class="chat-configuration-hint mcp-tool-mode-reset-description">${uiText(resetDescription).html}</span>` + `</div>` : '';
    return `<div class="mcp-tools-scope">` + `<div class="mcp-default-tools-title">${inputArguments.strings.toolsTitle}</div>` + `<div id="${listId}" class="mcp-tools-list"></div>` + `<div id="${emptyId}" class="mcp-tools-empty u-hidden">${inputArguments.strings.toolsEmpty}</div>` + resetToolsMarkup + `</div>`;
};

export { buildMcpConversationSettingsBodyMarkup, buildMcpDefaultToolsModalBodyMarkup };
export type { McpConversationDefaultToolsMarkup, McpConversationResetToolsMarkup, McpConversationSettingsMarkupStrings, McpConversationToggleMarkup, McpDefaultToolsModalBodyStrings };
