/* SoAI - Chat feature tool approval preview markup [frontend/assets/ts/features/chat/toolapproval/toolApprovalPreviewMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { ToolApprovalPrompt } from '@features/chat/toolapproval/toolApprovalModels.ts';
import type { MarkupEscaper } from '@features/chat/message/markupEscaper.ts';

type ToolApprovalPreviewMarkupDependencies = {
    messageManager: MarkupEscaper;
};

function buildToolApprovalPreviewMarkup(dependencies: ToolApprovalPreviewMarkupDependencies, prompt: ToolApprovalPrompt): TrustedHtml {
    const title = dependencies.messageManager.escapeHtml(i18n.t('chat.toolApproval.title'));
    const approveLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.toolApproval.approve'));
    const denyLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.toolApproval.deny'));
    const rememberLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.toolApproval.remember'));
    const toolLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.toolApproval.toolLabel'));
    const argumentsLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.toolApproval.argumentsLabel'));

    const taskIdAttr = dependencies.messageManager.escapeAttribute(prompt.taskId);
    const toolNameHtml = dependencies.messageManager.escapeHtml(prompt.toolName);

    const rememberToggleId = dependencies.messageManager.escapeAttribute(`tool_approval_remember_${prompt.taskId}`);
    const toolCallIdHtml = prompt.toolCallId ? dependencies.messageManager.escapeHtml(prompt.toolCallId) : '';
    const toolArgumentsHtml = prompt.toolArguments ? dependencies.messageManager.escapeHtml(prompt.toolArguments) : '';

    const header = `<div class="tool-approval-header"><div class="tool-approval-title">${title}</div></div>`;
    const toolLine = `<div class="tool-approval-line"><span class="tool-approval-label">${toolLabel}</span><span class="tool-approval-value">${toolNameHtml}</span></div>`;
    const callIdLine = toolCallIdHtml ? `<div class="tool-approval-line"><span class="tool-approval-label">${dependencies.messageManager.escapeHtml(i18n.t('chat.toolApproval.callIdLabel'))}</span><span class="tool-approval-value">${toolCallIdHtml}</span></div>` : '';
    const argumentsDetails = toolArgumentsHtml ? `<details class="tool-approval-arguments"><summary>${argumentsLabel}</summary><pre class="tool-approval-arguments-pre">${toolArgumentsHtml}</pre></details>` : '';
    const rememberToggle = `<div class="tool-approval-remember"><input type="checkbox" id="${rememberToggleId}" class="tool-approval-remember-toggle"><label for="${rememberToggleId}">${rememberLabel}</label></div>`;
    const footer = `<div class="tool-approval-footer"><button type="button" class="tool-approval-deny-btn ui-button ui-variant-danger" data-action="chat:tool-approval-deny" data-task-id="${taskIdAttr}" ${renderLabelAttributes(i18n.t('chat.toolApproval.deny'))}>${denyLabel}</button><button type="button" class="tool-approval-approve-btn ui-button ui-variant-success" data-action="chat:tool-approval-approve" data-task-id="${taskIdAttr}" ${renderLabelAttributes(i18n.t('chat.toolApproval.approve'))}>${approveLabel}</button></div>`;

    const body = `<div class="tool-approval-body">${toolLine}${callIdLine}${argumentsDetails}${rememberToggle}</div>`;

    return toTrustedUiHtml(`${header}${body}${footer}`);
}

export { buildToolApprovalPreviewMarkup };
