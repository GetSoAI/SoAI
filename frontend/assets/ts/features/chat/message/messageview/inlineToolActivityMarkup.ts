/* SoAI - Chat feature inline tool activity markup [frontend/assets/ts/features/chat/message/messageview/inlineToolActivityMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { renderInlineStatusIcon } from '@features/chat/message/messageview/inlineActivityStatusRendering.ts';
import { resolveInlineActivityName } from '@features/chat/message/messageview/inlineActivityName.ts';
import { resolveInlineToolHeaderQueryText } from '@features/chat/message/messageview/inlineToolActivityPayloadParsing.ts';
import { isInlineToolActivityExplicitlyNonExpandable, type InlineToolActivityPresentation } from '@features/chat/message/messageview/inlineToolActivityPresentation.ts';
import { renderInlineActivityChrome } from '@features/chat/message/messageview/inlineActivityChrome.ts';
import { renderInlineActivityHeaderRow, renderInlineActivityIcon, renderInlineActivityLeadingIcon, type InlineActivityStopButtonArguments } from '@features/chat/message/messageview/inlineActivityHeaderRow.ts';
import type { ChatMessageRenderHost, InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { CONTEXT_COMPACTION_TOOL_LEAF } from '@features/chat/message/contextcompaction/detection.ts';
import { resolveAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';

const renderToolIcon = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment, toolLeafName: string): string => {
    if (segment.status === 'error') {
        return renderInlineStatusIcon(host, segment.status, 'plugin');
    }
    if (toolLeafName === 'wait') {
        return renderInlineStatusIcon(host, segment.status, 'clock');
    }
    if (toolLeafName === CONTEXT_COMPACTION_TOOL_LEAF) {
        return renderInlineStatusIcon(host, segment.status, 'agent-compact');
    }
    const toolIconSvg = host.getToolIconHtml(segment.toolName);
    if (toolIconSvg) {
        return renderInlineActivityIcon({ innerHtml: toolIconSvg });
    }
    if (toolLeafName === 'subagent_spawn') {
        return renderInlineStatusIcon(host, segment.status, 'model-default');
    }
    return renderInlineStatusIcon(host, segment.status, 'plugin');
};

const resolveInlineToolStopButton = (segment: InlineToolActivitySegment, toolLeafName: string): InlineActivityStopButtonArguments | null => {
    if (toolLeafName !== 'shell' || segment.status !== 'running') {
        return null;
    }
    const assistantIdentity = resolveAssistantVariantIdentity({
        assistantTurnTimestamp: segment.assistantTurnAtMs,
        modelVariantIndex: segment.modelVariantIndex
    });
    if (assistantIdentity === null) {
        return null;
    }
    return {
        actionId: CHAT_ACTIONS.STOP_SHELL,
        callId: segment.callId,
        assistantTurnAtMs: assistantIdentity.assistantTurnTimestamp,
        modelVariantIndex: assistantIdentity.modelVariantIndex,
        label: i18n.t('chat.toolActivity.stopShellHeader')
    };
};

const renderInlineToolActivityMarkup = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment, details: { presentation: InlineToolActivityPresentation; detailsSignature: string }): string => {
    const isCollapsed = segment.collapsed !== false;
    const normalizedName = resolveInlineActivityName(segment);
    const toolLeafName = details.presentation.toolLeafName;
    const isContextCompaction = toolLeafName === CONTEXT_COMPACTION_TOOL_LEAF;
    const isTerminalContextCompaction = segment.status === 'completed' || segment.status === 'error';
    const isExplicitlyNonExpandable = isInlineToolActivityExplicitlyNonExpandable(toolLeafName);
    const isRunningExpandableTool = segment.status === 'running' && !isExplicitlyNonExpandable;
    const hasExpandableDetails = details.presentation.hasDetails || isRunningExpandableTool;
    const toggleEnabled = segment.status !== 'pending' && hasExpandableDetails && (!isContextCompaction || isTerminalContextCompaction);
    const leadingIconHtml = toggleEnabled ? renderInlineActivityLeadingIcon(host, { variant: 'expander', iconName: 'chevron-right', options: { size: 10, strokeWidth: 4 } }) : renderInlineActivityLeadingIcon(host, { variant: 'hourglass', iconName: 'hourglass', options: { size: 8, strokeWidth: 1.5 } });
    const openRequested = toggleEnabled && !isCollapsed;
    const chrome = renderInlineActivityChrome(host, {
        segment,
        mainIconHtml: renderToolIcon(host, segment, toolLeafName),
        previewText: resolveInlineToolHeaderQueryText(segment),
        expansionState: openRequested ? 'expanded' : 'collapsed'
    });
    const activityTypeClass = isContextCompaction ? ' inline-activity-context-compaction' : '';
    const activityClasses = `inline-activity inline-activity-type-tool${activityTypeClass} ${chrome.statusClass}`;
    const headerHtml = renderInlineActivityHeaderRow(host, {
        tagName: 'div',
        leadingIconHtml,
        statusLedHtml: chrome.statusDotHtml,
        mainIconHtml: chrome.mainIconHtml,
        name: normalizedName,
        previewHtml: chrome.previewHtml,
        durationHtml: chrome.durationHtml,
        actionId: toggleEnabled ? 'chat:toggle-tool-activity-item' : undefined,
        callId: segment.callId,
        toggleEnabled,
        expandedCloseButton: toggleEnabled,
        stopButton: resolveInlineToolStopButton(segment, toolLeafName)
    });
    const detailsSignature = hasExpandableDetails ? details.detailsSignature : '';
    const signatureAttr = hasExpandableDetails ? ` ${INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE}="${host.escapeAttribute(detailsSignature)}"` : '';
    const openRequestedAttr = openRequested ? ` ${INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE}="true"` : '';
    return `<div class="${activityClasses}" data-tool-leaf="${host.escapeAttribute(toolLeafName)}" data-call-id="${host.escapeAttribute(segment.callId)}"${signatureAttr}${openRequestedAttr} data-collapsed="true"${chrome.startedAtAttr}${chrome.settledDurationAttr}>${headerHtml}</div>`;
};

export { renderInlineToolActivityMarkup };
