/* SoAI - Chat feature tool call output modal rendering [frontend/assets/ts/features/chat/modals/toolcalloutputmodal/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderStructuredFields } from '@features/chat/message/messageview/inlineToolFieldRendering.ts';
import type { ToolCallOutputModalContentRender, ToolCallOutputModalEscapeDependencies, ToolCallOutputModalToolCall } from '@features/chat/modals/toolcalloutputmodal/types.ts';
import { resolveToolCallOutputPresentation } from '@features/chat/toolactivity/toolOutputPresentation.ts';

const renderToolCallOutputModalContent = (dependencies: ToolCallOutputModalEscapeDependencies, toolCall: ToolCallOutputModalToolCall): ToolCallOutputModalContentRender => {
    const presentation = resolveToolCallOutputPresentation(toolCall);
    const host = {
        escapeHtml: (value: string): string => dependencies.escapeHtml(value),
        escapeAttribute: (value: string): string => dependencies.escapeAttribute(value)
    };
    const rendered = renderStructuredFields(host, presentation.displayRecord, { depth: 0, scrollKeyPrefix: null, path: [] });
    const warningText = i18n.t('chat.toolCallOutputModal.outputDisplayLimitNotice');
    const warningHtml = presentation.hasDisplayTruncation ? `<div class="tool-call-output-modal-warning">${dependencies.escapeHtml(warningText)}</div>` : '';
    const loadMoreTooltip = dependencies.escapeAttribute(i18n.t('chat.toolCallOutputModal.loadMoreLiveHistory'));
    const loadMoreHtml = presentation.nextBeforeLiveSequence === null ? '' : ['<div class="tool-call-output-modal-live-history-actions">', `<button type="button" data-action="tool-call-live-history-load-more" aria-label="${loadMoreTooltip}" data-tooltip="${loadMoreTooltip}">`, dependencies.escapeHtml(i18n.t('chat.toolCallOutputModal.loadMoreLiveHistory')), '</button>', '</div>'].join('');
    return {
        html: `<div class="tool-call-output-modal-content">${warningHtml}${rendered}${loadMoreHtml}</div>`,
        copyText: presentation.copyText,
        nextBeforeLiveSequence: presentation.nextBeforeLiveSequence
    };
};

export { renderToolCallOutputModalContent };
