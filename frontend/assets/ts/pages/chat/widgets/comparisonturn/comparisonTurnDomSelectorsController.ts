/* SoAI - DOM selector constants for chat comparison turns [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnDomSelectorsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const CHAT_COMPARISON_MESSAGE_SELECTOR = '.chat-message.assistant[data-assistant-turn-ts][data-model-variant-index]';
const CHEVRON_PREV_SELECTOR = 'button.chat-comparison-chevron--prev[data-action="chat:comparison-prev"]';
const CHEVRON_NEXT_SELECTOR = 'button.chat-comparison-chevron--next[data-action="chat:comparison-next"]';
const CHAT_COMPARISON_TURN_SELECTOR = '.chat-comparison-turn[data-assistant-turn-ts][data-comparison-variant-total]';
const CHAT_COMPARISON_TURN_VIEWPORT_SELECTOR = ':scope > .chat-comparison-turn-viewport';
const CHAT_COMPARISON_TURN_TRACK_SELECTOR = ':scope > .chat-comparison-turn-viewport > .chat-comparison-turn-track';
const CHAT_COMPARISON_TURN_SLIDE_SELECTOR = ':scope > .chat-comparison-turn-slide[data-comparison-slide-index]';

export { CHAT_COMPARISON_MESSAGE_SELECTOR, CHAT_COMPARISON_TURN_SELECTOR, CHAT_COMPARISON_TURN_SLIDE_SELECTOR, CHAT_COMPARISON_TURN_TRACK_SELECTOR, CHAT_COMPARISON_TURN_VIEWPORT_SELECTOR, CHEVRON_NEXT_SELECTOR, CHEVRON_PREV_SELECTOR };
