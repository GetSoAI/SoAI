/* SoAI - Tool full-output action presentation [frontend/assets/ts/features/chat/message/messageview/toolOutputAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import { i18n } from '@core/i18n/index.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import type { ChatMessageRenderHost, InlineToolActivitySegment } from '@features/chat/message/messageview/types.ts';
import { resolveToolOutputTruncation } from '@features/chat/toolactivity/toolOutputPresentation.ts';

const renderToolOutputAction = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment): string => {
    if (segment.result === undefined || resolveToolOutputTruncation(segment.result) === null) return '';
    const identity = resolveAssistantVariantIdentity({ assistantTurnTimestamp: segment.assistantTurnAtMs, modelVariantIndex: segment.modelVariantIndex });
    if (identity === null) throw new Error('Tool output action requires assistantTurnTimestamp and modelVariantIndex.');
    const label = i18n.t('chat.toolActivity.viewFullOutput');
    return `<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="${host.escapeAttribute(CHAT_ACTIONS.OPEN_TOOL_CALL_OUTPUT)}" data-call-id="${host.escapeAttribute(segment.callId)}" data-assistant-turn-ts="${host.escapeAttribute(String(identity.assistantTurnTimestamp))}" data-model-variant-index="${host.escapeAttribute(String(identity.modelVariantIndex))}" aria-label="${host.escapeAttribute(label)}" data-tooltip="${host.escapeAttribute(label)}">${host.escapeHtml(label)}</button>`;
};

export { renderToolOutputAction };
