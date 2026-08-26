/* SoAI - Chat feature render message header role markup [frontend/assets/ts/features/chat/message/messageview/renderMessageHeaderRoleMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { renderAssistantHeaderActivity } from '@features/chat/message/messageview/assistantHeaderActivity.ts';
import { renderRoleBadgeText } from '@features/chat/message/chatMessageAvatarMarkup.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

export const renderMessageHeaderRoleMarkup = (
    dependencies: {
        escapeHtml: (value: string) => string;
        escapeAttribute: (value: string) => string;
        getIconHtml: (name: IconName, options?: IconOptions) => string;
        nowMs: () => number;
        getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
    },
    inputArguments: {
        role: string;
        senderLabel: string;
        messageModelId: string | null;
        modelTypeLabel: string | null;
        comparisonTurn: ChatComparisonTurnRenderModel | null;
        message: ChatMessage;
    }
): string => {
    const roleHeaderHtml =
        inputArguments.role === 'assistant'
            ? renderAssistantHeaderActivity(
                  {
                      escapeHtml: dependencies.escapeHtml,
                      escapeAttribute: dependencies.escapeAttribute,
                      getIconHtml: dependencies.getIconHtml,
                      nowMs: dependencies.nowMs,
                      getActivityDurationDisplayMode: dependencies.getActivityDurationDisplayMode
                  },
                  inputArguments.senderLabel,
                  inputArguments.messageModelId,
                  inputArguments.modelTypeLabel,
                  inputArguments.message,
                  inputArguments.comparisonTurn
              )
            : renderRoleBadgeText({ escapeHtml: dependencies.escapeHtml }, inputArguments.senderLabel);

    const comparisonNavHtml =
        inputArguments.role === 'assistant' && inputArguments.comparisonTurn !== null && inputArguments.comparisonTurn.invalidReason === null
            ? (() => {
                  const prevLabel = dependencies.escapeAttribute(i18n.t('chat.comparison.navigation.previous'));
                  const nextLabel = dependencies.escapeAttribute(i18n.t('chat.comparison.navigation.next'));
                  const prevIcon = dependencies.getIconHtml('chevron-left', { size: 16, strokeWidth: 1.5 });
                  const nextIcon = dependencies.getIconHtml('chevron-right', { size: 16, strokeWidth: 1.5 });
                  const assistantTurnAttr = dependencies.escapeAttribute(String(inputArguments.comparisonTurn.assistantTurnTimestamp));
                  const activeAttr = dependencies.escapeAttribute(String(inputArguments.comparisonTurn.activeVariantIndex));
                  const totalAttr = dependencies.escapeAttribute(String(inputArguments.comparisonTurn.variantCount));
                  const hasPrev = inputArguments.comparisonTurn.activeVariantIndex > 0;
                  const hasNext = inputArguments.comparisonTurn.activeVariantIndex < inputArguments.comparisonTurn.variantCount - 1;
                  const prevHiddenAttribute = hasPrev ? '' : ' hidden aria-hidden="true"';
                  const nextHiddenAttribute = hasNext ? '' : ' hidden aria-hidden="true"';
                  const prevDisabledAttribute = hasPrev ? '' : ' disabled';
                  const nextDisabledAttribute = hasNext ? '' : ' disabled';
                  const sharedAttrs = ` data-assistant-turn-ts="${assistantTurnAttr}" data-comparison-active-variant-index="${activeAttr}" data-comparison-variant-total="${totalAttr}"`;
                  const prevButton = `<button type="button" class="chat-comparison-chevron chat-comparison-chevron--prev" data-action="${CHAT_ACTIONS.COMPARISON_PREV}"${sharedAttrs} aria-label="${prevLabel}" data-tooltip="${prevLabel}"${prevHiddenAttribute}${prevDisabledAttribute}>` + `${prevIcon}` + `</button>`;
                  const nextButton = `<button type="button" class="chat-comparison-chevron chat-comparison-chevron--next" data-action="${CHAT_ACTIONS.COMPARISON_NEXT}"${sharedAttrs} aria-label="${nextLabel}" data-tooltip="${nextLabel}"${nextHiddenAttribute}${nextDisabledAttribute}>` + `${nextIcon}` + `</button>`;
                  return prevButton + nextButton;
              })()
            : '';

    if (!comparisonNavHtml) {
        return roleHeaderHtml;
    }
    return `<span class="message-role-comparison-nav">${roleHeaderHtml}${comparisonNavHtml}</span>`;
};
