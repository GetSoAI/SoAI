/* SoAI - Shared chat-body text eligibility for find and selection [frontend/assets/ts/features/chat/message/searchTextPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchTextTraversalPolicy } from '@core/search/domTextIndex.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveNormalizedMessageRole } from '@features/chat/message/messageRole.ts';

const SEARCH_EXCLUDED_SUBTREES = 'script, style, template, noscript, svg, math, annotation, button, input, textarea, select, audio, video, canvas, iframe, object, embed, [contenteditable], [hidden], .u-hidden, .katex-mathml, .inline-activity, .inline-activity-details, .inline-action-update, .tool-call, .message-thinking-phase, .message-header, .message-actions, .message-error, .message-output-notice, .message-deleted-badge, .message-deleted-actions, .chat-attachment-summary-card, .message-attachment-strip, .chat-inline-media-card, .chat-inline-media-reference, .message-image, .mermaid-container, .footnote-backref, .sort-indicator, .speech-setup-placeholder, .assistant-activity-widgets';
const SEARCH_BLOCK_BOUNDARIES = 'p, div, section, article, h1, h2, h3, h4, h5, h6, li, td, th, pre, blockquote, br, hr';

const isSearchableChatMessage = (message: ChatMessage): boolean => {
    const role = resolveNormalizedMessageRole(message);
    return (message.messageType === undefined || message.messageType === 'chat') && (role === 'user' || role === 'assistant');
};

const chatSearchTextTraversalPolicy: SearchTextTraversalPolicy = (element) => {
    if (element.matches(SEARCH_EXCLUDED_SUBTREES)) return 'exclude';
    return element.matches(SEARCH_BLOCK_BOUNDARIES) ? 'boundary' : 'inline';
};

const presentedChatSearchTextTraversalPolicy: SearchTextTraversalPolicy = (element) => {
    const structural = chatSearchTextTraversalPolicy(element);
    if (structural === 'exclude') return structural;
    const style = element.ownerDocument.defaultView?.getComputedStyle(element);
    return style?.display === 'none' || style?.visibility === 'hidden' || style?.visibility === 'collapse' ? 'exclude' : structural;
};

export { chatSearchTextTraversalPolicy, presentedChatSearchTextTraversalPolicy, isSearchableChatMessage };
