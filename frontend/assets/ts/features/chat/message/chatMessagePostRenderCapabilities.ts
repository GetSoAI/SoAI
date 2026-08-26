/* SoAI - Canonical chat message post-render capability contract [frontend/assets/ts/features/chat/message/chatMessagePostRenderCapabilities.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { PREVIEW_REFERENCE_START } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';

const CHAT_POST_RENDER_CAPABILITIES_ATTRIBUTE = 'data-chat-post-render-capabilities';
const MERMAID_CONTAINER_CLASS = 'mermaid-container';
const CHAT_BRANDING_LOGO_CLASS = 'assistant-activity-widget__brand-logo';
const INLINE_TOOL_IMAGE_CLASS = 'inline-tool-image';
const ASSISTANT_ARTICLE_IMAGE_CLASS = 'assistant-news-widget__image';
const INLINE_MULTIMEDIA_CARD_CLASS = 'chat-inline-media-card';
const CHAT_CODE_BLOCK_SELECTOR = 'pre:not([data-code-highlighted="true"])';
const CHAT_BRANDING_LOGO_SELECTOR = `.${CHAT_BRANDING_LOGO_CLASS}[data-logo-type]`;
const INLINE_TOOL_IMAGE_SELECTOR = `.${INLINE_TOOL_IMAGE_CLASS} img`;
const ASSISTANT_ARTICLE_IMAGE_SELECTOR = `.assistant-news-widget__media .${ASSISTANT_ARTICLE_IMAGE_CLASS}`;
const CHAT_IMAGE_LIFECYCLE_SELECTOR = `${INLINE_TOOL_IMAGE_SELECTOR}, ${ASSISTANT_ARTICLE_IMAGE_SELECTOR}`;
const ENABLED_INLINE_MULTIMEDIA_SELECTOR = `.${INLINE_MULTIMEDIA_CARD_CLASS}__media, .${INLINE_MULTIMEDIA_CARD_CLASS}[data-inline-media-card="1"], img`;
const DISABLED_INLINE_MULTIMEDIA_SELECTOR = 'a[href], img';
const STREAMING_POST_RENDER_MARKER_SELECTOR = `pre, a, img, .${MERMAID_CONTAINER_CLASS}, [data-inline-media-card="1"]`;

type ChatPostRenderCapability = 'code' | 'mermaid' | 'branding' | 'image-lifecycle' | 'inline-multimedia';
const CHAT_POST_RENDER_CAPABILITY_ORDER: readonly ChatPostRenderCapability[] = ['code', 'mermaid', 'branding', 'image-lifecycle', 'inline-multimedia'];

type ChatPostRenderCapabilities = ReadonlySet<ChatPostRenderCapability>;

const isChatPostRenderCapability = (value: string): value is ChatPostRenderCapability => {
    return value === 'code' || value === 'mermaid' || value === 'branding' || value === 'image-lifecycle' || value === 'inline-multimedia';
};

const serializeChatPostRenderCapabilities = (capabilities: ReadonlySet<ChatPostRenderCapability>): string => {
    return CHAT_POST_RENDER_CAPABILITY_ORDER.filter((capability) => capabilities.has(capability)).join(' ');
};

const containsRenderedElement = (markup: string, tagName: string): boolean => {
    return markup.includes(`<${tagName}>`) || markup.includes(`<${tagName} `);
};

const classifyChatMessagePostRenderCapabilities = (markup: string): ReadonlySet<ChatPostRenderCapability> => {
    const capabilities = new Set<ChatPostRenderCapability>();
    if (containsRenderedElement(markup, 'pre')) capabilities.add('code');
    if (markup.includes(MERMAID_CONTAINER_CLASS)) capabilities.add('mermaid');
    if (markup.includes(CHAT_BRANDING_LOGO_CLASS)) capabilities.add('branding');
    if (markup.includes(INLINE_TOOL_IMAGE_CLASS) || markup.includes(ASSISTANT_ARTICLE_IMAGE_CLASS)) capabilities.add('image-lifecycle');
    if (containsRenderedElement(markup, 'img') || containsRenderedElement(markup, 'a') || markup.includes(INLINE_MULTIMEDIA_CARD_CLASS) || markup.includes(PREVIEW_REFERENCE_START)) capabilities.add('inline-multimedia');
    return capabilities;
};

const classifyChatPostRenderCapabilitiesFromDom = (element: HTMLElement): ReadonlySet<ChatPostRenderCapability> => {
    const capabilities = new Set<ChatPostRenderCapability>();
    const candidates = dom.resolveAll(STREAMING_POST_RENDER_MARKER_SELECTOR, element).filter((candidate): candidate is HTMLElement => candidate instanceof HTMLElement);
    for (const candidate of candidates) {
        if (candidate.matches('pre')) capabilities.add('code');
        if (candidate.classList.contains(MERMAID_CONTAINER_CLASS)) capabilities.add('mermaid');
        if (candidate.matches(CHAT_BRANDING_LOGO_SELECTOR)) capabilities.add('branding');
        if (candidate.matches(CHAT_IMAGE_LIFECYCLE_SELECTOR)) capabilities.add('image-lifecycle');
        if (candidate.matches('a, img, [data-inline-media-card="1"]')) capabilities.add('inline-multimedia');
    }
    return capabilities;
};

const renderChatPostRenderCapabilitiesAttribute = (markup: string): string => {
    const serialized = serializeChatPostRenderCapabilities(classifyChatMessagePostRenderCapabilities(markup));
    return ` ${CHAT_POST_RENDER_CAPABILITIES_ATTRIBUTE}="${serialized}"`;
};

const readChatPostRenderCapabilities = (element: HTMLElement): ChatPostRenderCapabilities | null => {
    const serialized = element.getAttribute(CHAT_POST_RENDER_CAPABILITIES_ATTRIBUTE);
    if (serialized === null) return null;
    if (serialized === '') return new Set();
    const tokens = serialized.split(' ');
    const capabilities = new Set<ChatPostRenderCapability>();
    for (const token of tokens) {
        if (!isChatPostRenderCapability(token) || capabilities.has(token)) return null;
        capabilities.add(token);
    }
    if (serializeChatPostRenderCapabilities(capabilities) !== serialized) return null;
    return capabilities;
};

const hasChatPostRenderCapability = (capabilities: ChatPostRenderCapabilities | null, capability: ChatPostRenderCapability): boolean => capabilities === null || capabilities.has(capability);

export { ASSISTANT_ARTICLE_IMAGE_SELECTOR, CHAT_BRANDING_LOGO_SELECTOR, CHAT_CODE_BLOCK_SELECTOR, CHAT_IMAGE_LIFECYCLE_SELECTOR, CHAT_POST_RENDER_CAPABILITIES_ATTRIBUTE, DISABLED_INLINE_MULTIMEDIA_SELECTOR, ENABLED_INLINE_MULTIMEDIA_SELECTOR, INLINE_TOOL_IMAGE_SELECTOR, STREAMING_POST_RENDER_MARKER_SELECTOR, classifyChatMessagePostRenderCapabilities, classifyChatPostRenderCapabilitiesFromDom, hasChatPostRenderCapability, readChatPostRenderCapabilities, renderChatPostRenderCapabilitiesAttribute, serializeChatPostRenderCapabilities };
export type { ChatPostRenderCapabilities, ChatPostRenderCapability };
