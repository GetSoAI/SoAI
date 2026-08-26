/* SoAI - Chat feature render markdown [frontend/assets/ts/features/chat/message/messageview/renderMarkdown.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { RichTextTableMode } from '@core/richtextrenderer/service.ts';
import { CHAT_ACTIONS } from '@features/chat/chatActionIds.ts';
import { renderInlineMediaPendingCardHtml } from '@features/chat/message/enhancers/inlineMultimediaPendingCard.ts';
import { PREVIEW_REFERENCE_PATTERN, PREVIEW_REFERENCE_START, normalizeIndentedPreviewReferenceTokenLines, parsePreviewReferenceTokenMatch, parseTrailingPreviewReferenceDraft } from '@features/chat/message/enhancers/inlineMultimediaPreviewContract.ts';
import { resolveInlineMultimediaPreviewTokenRoute } from '@features/chat/message/enhancers/inlineMultimediaPreviewTokenResolution.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';

const FENCED_CODE_BLOCK_MARKER_PATTERN = /^```/;

const wrapIconHtml = (iconHtml: string): string => {
    const trimmed = iconHtml.trim();
    if (!trimmed) {
        return '';
    }
    return `<span class="ui-icon" aria-hidden="true">${trimmed}</span>`;
};

const renderMessageCodeBlock = (host: ChatMessageRenderHost, descriptor: { html: string; value: string }): string => {
    const copyLabel = host.escapeAttribute(i18n.t('chat.message.actions.copyCode'));
    const copyIcon = wrapIconHtml(host.getIconHtml('copy', { size: 14, strokeWidth: 1.5 }));
    const encoded = host.escapeAttribute(encodeURIComponent(descriptor.value));
    const button = `<button type="button" class="code-copy-btn ui-icon-button ui-icon-button-small ui-variant-neutral" data-action="chat:copy-code-block" aria-label="${copyLabel}" data-tooltip="${copyLabel}" data-code="${encoded}">${copyIcon}</button>`;
    return `<div class="message-code-block">${descriptor.html}${button}</div>`;
};

const PREVIEW_TOKEN_PLACEHOLDER_PREFIX = '\uE002SOAI_PREVIEW_';
const PREVIEW_TOKEN_PLACEHOLDER_SUFFIX = '\uE003';

const protectInlinePreviewTokens = (host: ChatMessageRenderHost, content: string): { protectedContent: string; restore: (html: string) => string } => {
    PREVIEW_REFERENCE_PATTERN.lastIndex = 0;
    let nextIndex = 0;
    const placeholderByToken = new Map<string, string>();
    const protectedContent = content.replace(PREVIEW_REFERENCE_PATTERN, (rawToken) => {
        const placeholder = `${PREVIEW_TOKEN_PLACEHOLDER_PREFIX}${nextIndex}${PREVIEW_TOKEN_PLACEHOLDER_SUFFIX}`;
        placeholderByToken.set(placeholder, rawToken);
        nextIndex += 1;
        return placeholder;
    });
    const trailingDraft = parseTrailingPreviewReferenceDraft(protectedContent);
    const protectedContentWithDraft = (() => {
        if (!trailingDraft) {
            return protectedContent;
        }
        const placeholder = `${PREVIEW_TOKEN_PLACEHOLDER_PREFIX}${nextIndex}${PREVIEW_TOKEN_PLACEHOLDER_SUFFIX}`;
        placeholderByToken.set(placeholder, trailingDraft.raw);
        const draftStartIndex = protectedContent.lastIndexOf(trailingDraft.raw);
        if (draftStartIndex < 0) {
            return protectedContent;
        }
        nextIndex += 1;
        return `${protectedContent.slice(0, draftStartIndex)}${placeholder}`;
    })();
    if (placeholderByToken.size <= 0) {
        return {
            protectedContent: content,
            restore: (html: string) => html
        };
    }
    return {
        protectedContent: protectedContentWithDraft,
        restore: (html: string) => {
            let restoredHtml = html;
            for (const [placeholder, rawToken] of placeholderByToken.entries()) {
                restoredHtml = restoredHtml.split(placeholder).join(host.escapeHtml(rawToken));
            }
            return restoredHtml;
        }
    };
};

const normalizeIndentedPreviewTokenLines = (content: string): string => {
    return normalizeIndentedPreviewReferenceTokenLines(content, {
        isCodeFenceLine: (line) => FENCED_CODE_BLOCK_MARKER_PATTERN.test(line.trimStart())
    });
};

const renderPlainTextContent = (host: ChatMessageRenderHost, content: string): string => {
    const escaped = host.escapeHtml(content);
    return `<p>${escaped.replace(/\n/g, '<br>')}</p>`;
};

type MarkdownRenderOptions = { tableMode?: RichTextTableMode; sortableTables?: boolean };

const renderMarkdownTextChunk = (host: ChatMessageRenderHost, content: string, options: MarkdownRenderOptions): string => {
    if (!content) {
        return '';
    }
    if (!host.isRichTextEnabled()) {
        return renderPlainTextContent(host, content);
    }
    const protectedTokens = protectInlinePreviewTokens(host, content);
    const tableModeOptions = options.tableMode === undefined ? {} : { tableMode: options.tableMode };
    const tableSortOptions = options.sortableTables === true ? { tableSortAction: CHAT_ACTIONS.SORT_MARKDOWN_TABLE } : {};
    return protectedTokens.restore(
        host.renderRichText(protectedTokens.protectedContent, (descriptor) => renderMessageCodeBlock(host, descriptor), {
            ...tableModeOptions,
            ...tableSortOptions
        })
    );
};

const renderPendingPreviewCardFromMatch = (host: ChatMessageRenderHost, rawMatch: RegExpMatchArray): string => {
    const token = parsePreviewReferenceTokenMatch(rawMatch);
    if (token === null) {
        return host.escapeHtml(String(rawMatch[0] ?? ''));
    }
    const routedToken = resolveInlineMultimediaPreviewTokenRoute(token);
    return renderInlineMediaPendingCardHtml(host, {
        type: routedToken.type,
        target: routedToken.target,
        label: routedToken.label,
        raw: routedToken.raw
    });
};

const renderMarkdownContentWithPreviewCards = (host: ChatMessageRenderHost, content: string, options: MarkdownRenderOptions): string => {
    const parts: string[] = [];
    let pendingText = '';
    let isInsideFencedCodeBlock = false;
    const lines = content.split('\n');
    const flushPendingText = (): void => {
        if (!pendingText) {
            return;
        }
        parts.push(renderMarkdownTextChunk(host, pendingText, options));
        pendingText = '';
    };
    for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
        const line = lines[lineIndex] ?? '';
        const newline = lineIndex < lines.length - 1 ? '\n' : '';
        if (FENCED_CODE_BLOCK_MARKER_PATTERN.test(line.trimStart())) {
            pendingText += `${line}${newline}`;
            isInsideFencedCodeBlock = !isInsideFencedCodeBlock;
            continue;
        }
        if (isInsideFencedCodeBlock || !line.includes(PREVIEW_REFERENCE_START)) {
            pendingText += `${line}${newline}`;
            continue;
        }
        PREVIEW_REFERENCE_PATTERN.lastIndex = 0;
        let lastIndex = 0;
        for (const rawMatch of line.matchAll(PREVIEW_REFERENCE_PATTERN)) {
            const matchIndex = rawMatch.index;
            const rawToken = String(rawMatch[0] ?? '');
            if (matchIndex === undefined || !rawToken) {
                continue;
            }
            pendingText += line.slice(lastIndex, matchIndex);
            flushPendingText();
            parts.push(renderPendingPreviewCardFromMatch(host, rawMatch));
            lastIndex = matchIndex + rawToken.length;
        }
        pendingText += `${line.slice(lastIndex)}${newline}`;
    }
    flushPendingText();
    return parts.join('');
};

const renderMarkdownContent = (host: ChatMessageRenderHost, content: string, options: MarkdownRenderOptions = {}): string => {
    const normalizedContent = normalizeIndentedPreviewTokenLines(content);
    if (host.isInlineMultimediaPreviewsEnabled() && normalizedContent.includes(PREVIEW_REFERENCE_START)) {
        return renderMarkdownContentWithPreviewCards(host, normalizedContent, options);
    }
    return renderMarkdownTextChunk(host, normalizedContent, options);
};

export { renderMarkdownContent, renderMessageCodeBlock };
