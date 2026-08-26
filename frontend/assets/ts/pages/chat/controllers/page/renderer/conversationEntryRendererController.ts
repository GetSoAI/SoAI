/* SoAI - Centralized markup rendering for conversation entries [frontend/assets/ts/pages/chat/controllers/page/renderer/conversationEntryRendererController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { ComparisonTurnVariantEntry, ConversationRenderEntry } from '@features/chat/public.ts';
import type { ChatCurrentConversationRenderDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';

const renderVariantSlide = (host: ChatCurrentConversationRenderDependencies, variant: ComparisonTurnVariantEntry): TrustedHtml => {
    if (variant.message === null || variant.messageIndex === null || variant.comparisonTurn === null) {
        return uiHtml`<div class="chat-comparison-turn-slide" data-comparison-slide-index="${uiAttr(variant.variantIndex)}" aria-hidden="true" inert><div class="chat-comparison-turn-placeholder glass-surface-strong glass-surface--no-shadow"><div class="chat-comparison-turn-placeholder-text">${uiText(i18n.t('chat.message.waiting'))}</div></div></div>`;
    }
    if (variant.presentation === null) {
        throw new Error('Chat comparison slide presentation is missing');
    }
    const markup = host.conversationRuntime.requireMessages().renderMessage({ message: variant.message, index: variant.messageIndex, comparisonTurn: variant.comparisonTurn, presentation: variant.presentation });
    return uiHtml`<div class="chat-comparison-turn-slide" data-comparison-slide-index="${uiAttr(variant.variantIndex)}" aria-hidden="true" inert><div class="chat-comparison-turn-slide-content" data-assistant-message-id="${uiAttr(variant.domId ?? '')}">${markup}</div></div>`;
};

export const renderConversationEntryMarkup = (host: ChatCurrentConversationRenderDependencies, entry: ConversationRenderEntry): TrustedHtml => {
    if (entry.type === 'message') {
        return host.conversationRuntime.requireMessages().renderMessage({ message: entry.message, index: entry.index, comparisonTurn: entry.comparisonTurn, presentation: entry.presentation });
    }

    const slides = entry.variants.map((variant) => renderVariantSlide(host, variant));
    return uiHtml`<div class="chat-comparison-turn" data-id="${uiAttr(entry.domId)}" data-assistant-turn-ts="${uiAttr(entry.assistantTurnTimestamp)}" data-comparison-variant-total="${uiAttr(entry.variantCount)}"><div class="chat-comparison-turn-viewport"><div class="chat-comparison-turn-track">${slides.reduce((markup, slide) => uiHtml`${markup}${slide}`, uiHtml``)}</div></div></div>`;
};
