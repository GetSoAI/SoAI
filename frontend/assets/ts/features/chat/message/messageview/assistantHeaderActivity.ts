/* SoAI - Chat feature assistant header activity [frontend/assets/ts/features/chat/message/messageview/assistantHeaderActivity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsNumber } from '@core/time/epochMs.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { CHAT_ACTION_ID_OPEN_MODEL_DETAIL } from '@features/chat/chatConstants.ts';
import type { ChatComparisonTurnRenderModel } from '@features/chat/comparisonTurnRenderModel.ts';
import { ASSISTANT_RESPONSE_STATUS_ATTRIBUTE } from '@features/chat/message/assistantHeaderCatalogStatus.ts';
import { renderAssistantHeaderDuration, resolveAssistantHeaderDurationArguments } from '@features/chat/message/messageview/assistantHeaderDuration.ts';
import { renderInlineActivityHeaderRow, renderInlineActivityIcon, renderInlineActivityLeadingIcon, renderInlineActivityPreview } from '@features/chat/message/messageview/inlineActivityHeaderRow.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

const resolveAssistantActivityModelIndexText = (comparisonTurn: ChatComparisonTurnRenderModel | null): string => {
    const modelVariantIndex = comparisonTurn ? comparisonTurn.modelVariantIndex : 0;
    const normalized = Number.isInteger(modelVariantIndex) && modelVariantIndex >= 0 ? modelVariantIndex : 0;
    const oneBased = normalized + 1;
    if (oneBased <= 1) {
        return '1';
    }
    if (oneBased >= 5) {
        return '5';
    }
    return String(oneBased);
};

const renderAssistantHeaderActivity = (
    dependencies: {
        escapeHtml: (value: string) => string;
        escapeAttribute: (value: string) => string;
        getIconHtml: (name: IconName, options?: IconOptions) => string;
        nowMs: () => number;
        getActivityDurationDisplayMode: () => ChatActivityDurationDisplayMode;
    },
    senderLabel: string,
    modelId: string | null,
    modelTypeLabel: string | null,
    message: ChatMessage,
    comparisonTurn: ChatComparisonTurnRenderModel | null
): string => {
    const isComparisonVariant = comparisonTurn !== null && comparisonTurn.invalidReason === null && comparisonTurn.variantCount > 1;
    const modelVariantIndex = isComparisonVariant && comparisonTurn ? comparisonTurn.modelVariantIndex : 0;
    const variantIndexAttr = ` data-model-variant-index="${String(modelVariantIndex)}"`;
    const activityLabel = senderLabel;

    const leadingIconHtml = renderInlineActivityLeadingIcon(dependencies, {
        variant: 'dot',
        iconName: 'dot-leading',
        options: { size: 12, strokeWidth: 1.5 },
        overlayText: resolveAssistantActivityModelIndexText(comparisonTurn),
        overlayAttributes: `data-model-leading-index="true"`
    });
    const statusLed = '<span class="inline-activity-status-led" data-model-status-led="true" aria-hidden="true"></span>';
    const modelIcon = dependencies.getIconHtml('model-default', { size: 16, strokeWidth: 1.5 });
    const iconHtml = renderInlineActivityIcon({ innerHtml: modelIcon });
    const modelIdAttr = modelId ? ` data-model-id="${dependencies.escapeAttribute(modelId)}"` : '';
    const modePreview = renderInlineActivityPreview(dependencies, {
        text: modelTypeLabel ?? '',
        rootAttributes: `data-model-mode="true"`,
        rootClassName: 'message-role-activity-model-mode',
        textAttributes: `data-model-mode-text="true"`,
        hidden: modelTypeLabel === null
    });
    const nowMs = dependencies.nowMs();
    const durationHtml = dependencies.getActivityDurationDisplayMode() === 'all' ? renderAssistantHeaderDuration((value: string): string => dependencies.escapeHtml(value), message, nowMs) : '';
    const durationArguments = resolveAssistantHeaderDurationArguments(message, nowMs);
    const startedAtMs = durationArguments?.startedAtMs;
    const startedAtAttr = durationArguments?.status === 'running' && typeof startedAtMs === 'number' && isEpochMsNumber(startedAtMs) ? ` data-assistant-started-at-ms="${dependencies.escapeAttribute(String(startedAtMs))}"` : '';
    const responseStatusAttr = durationArguments ? ` ${ASSISTANT_RESPONSE_STATUS_ATTRIBUTE}="${durationArguments.status}"` : '';
    const statusClassName = durationArguments?.status === 'running' ? ' inline-activity-status-running' : durationArguments?.status === 'completed' ? ' inline-activity-status-completed' : '';
    const headerHtml = renderInlineActivityHeaderRow(dependencies, {
        tagName: 'span',
        leadingIconHtml,
        statusLedHtml: statusLed,
        mainIconHtml: iconHtml,
        name: activityLabel,
        previewHtml: modePreview,
        durationHtml,
        separatorDotHidden: modelTypeLabel === null,
        toggleEnabled: false
    });
    const modelActionAttr = modelId ? ` data-action="${CHAT_ACTION_ID_OPEN_MODEL_DETAIL}"` : '';
    const titleAttr = activityLabel.trim() ? ` data-tooltip="${dependencies.escapeAttribute(activityLabel)}"` : '';
    return `<span class="message-role-activity inline-activity${statusClassName}" data-collapsed="true"${modelIdAttr}${variantIndexAttr}${startedAtAttr}${responseStatusAttr}${modelActionAttr}${titleAttr}>${headerHtml}</span>`;
};

export { renderAssistantHeaderActivity };
