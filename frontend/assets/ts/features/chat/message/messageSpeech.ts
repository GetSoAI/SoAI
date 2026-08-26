/* SoAI - Chat feature message speech [frontend/assets/ts/features/chat/message/messageSpeech.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { securityApi } from '@core/security/public.ts';
import { replaceChildrenFromHtml } from '@core/dom/html.ts';
import { beginLoadingButton, endLoadingButton } from '@core/ui/loadingbuttons/service.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { SPEECH_EXCLUDE_ATTRIBUTE } from '@features/chat/message/speechConstants.ts';

type SpeakButtonLoadingToken = string;
type SpeakButtonMode = 'speak' | 'stop';
const SPEECH_EXCLUDED_SELECTOR = ['button', 'svg', '[aria-hidden="true"]', `[${SPEECH_EXCLUDE_ATTRIBUTE}="true"]`, '.inline-activity', '.inline-action-update', '.tool-call'].join(', ');
const MARKDOWN_HEADING_PATTERN = /^#{1,6}(?:\s+|$)/gm;
const MARKDOWN_BLOCKQUOTE_PATTERN = /^>\s?/gm;
const MARKDOWN_BULLET_PATTERN = /^(\s*)[-+*](?:\s+|$)/gm;
const MARKDOWN_STRONG_MARKER_PATTERN = /\*\*|__|~~|`/g;
const MARKDOWN_LEADING_EMPHASIS_PATTERN = /(^|[\s([{])\*(?=\S)/g;
const MARKDOWN_TRAILING_EMPHASIS_PATTERN = /(\S)\*(?=$|[\s.,;:!?)}\]])/g;

function setSpeakButtonLoading(button: HTMLButtonElement, isLoading: true): SpeakButtonLoadingToken;
function setSpeakButtonLoading(button: HTMLButtonElement, isLoading: false, token: SpeakButtonLoadingToken): void;
function setSpeakButtonLoading(button: HTMLButtonElement, isLoading: boolean, token?: SpeakButtonLoadingToken): SpeakButtonLoadingToken | void {
    if (isLoading) {
        return beginLoadingButton(button);
    }

    if (typeof token !== 'string' || token.length === 0) {
        throw new Error('setSpeakButtonLoading requires a token to clear loading');
    }
    return endLoadingButton(button, token);
}

const setSpeakButtonMode = (button: HTMLButtonElement, mode: SpeakButtonMode): void => {
    const speakLabel = button.dataset['speakLabel'];
    const stopLabel = button.dataset['stopLabel'];
    if (!speakLabel || !stopLabel) {
        throw new Error('Speak button requires both data-speak-label and data-stop-label');
    }
    const resolvedLabel = mode === 'stop' ? stopLabel : speakLabel;
    button.classList.toggle('is-stop-mode', mode === 'stop');
    setTooltipText(button, resolvedLabel);
    button.setAttribute('aria-label', resolvedLabel);
};

const normalizeSpeechTextLines = (value: string): string => {
    const lines = value
        .replace(/\r/g, '')
        .split('\n')
        .map((line) => line.replace(/\s+/g, ' ').trim());
    const normalizedLines: string[] = [];
    for (const line of lines) {
        if (!line) {
            if (normalizedLines.length && normalizedLines[normalizedLines.length - 1] !== '') {
                normalizedLines.push('');
            }
            continue;
        }
        normalizedLines.push(line);
    }
    return normalizedLines.join('\n').trim();
};

const stripMarkdownResidueForSpeech = (value: string): string => {
    const withoutBlockMarkers = value.replace(MARKDOWN_HEADING_PATTERN, '').replace(MARKDOWN_BLOCKQUOTE_PATTERN, '').replace(MARKDOWN_BULLET_PATTERN, '$1');
    const withoutInlineMarkers = withoutBlockMarkers.replace(MARKDOWN_STRONG_MARKER_PATTERN, '').replace(MARKDOWN_LEADING_EMPHASIS_PATTERN, '$1').replace(MARKDOWN_TRAILING_EMPHASIS_PATTERN, '$1');
    return normalizeSpeechTextLines(withoutInlineMarkers);
};

const extractSpeechTextFromHtml = (html: string): string => {
    const container = document.createElement('div');
    replaceChildrenFromHtml({ element: container, html: securityApi.sanitizeHtml(html), context: container });

    for (const element of dom.resolveAll(SPEECH_EXCLUDED_SELECTOR, container)) {
        element.remove();
    }

    const blockTags = new Set<string>(['P', 'DIV', 'LI', 'PRE', 'BLOCKQUOTE', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'UL', 'OL', 'TABLE', 'TR']);

    const parts: string[] = [];
    const ensureTrailingNewline = (): void => {
        const last = parts.length ? parts[parts.length - 1] : '';
        if (last && !last.endsWith('\n')) {
            parts.push('\n');
        }
    };

    const visit = (node: Node): void => {
        if (node.nodeType === Node.TEXT_NODE) {
            const value = node.textContent ?? '';
            if (value) {
                parts.push(value);
            }
            return;
        }
        if (!(node instanceof Element)) {
            return;
        }
        const tagName = node.tagName.toUpperCase();
        if (tagName === 'BR') {
            parts.push('\n');
            return;
        }
        if (tagName === 'HR') {
            ensureTrailingNewline();
            return;
        }
        if (tagName === 'SCRIPT' || tagName === 'STYLE') {
            return;
        }
        const isBlock = blockTags.has(tagName);
        if (isBlock) {
            ensureTrailingNewline();
        }
        for (const child of Array.from(node.childNodes)) {
            visit(child);
        }
        if (tagName === 'TD' || tagName === 'TH') {
            parts.push(' ');
        }
        if (isBlock) {
            ensureTrailingNewline();
        }
    };

    for (const child of Array.from(container.childNodes)) {
        visit(child);
    }

    return normalizeSpeechTextLines(parts.join(''));
};

const extractSpeechTextFromMarkdown = (markdown: string): string => {
    return stripMarkdownResidueForSpeech(markdown);
};

export { extractSpeechTextFromHtml, extractSpeechTextFromMarkdown, setSpeakButtonLoading, setSpeakButtonMode, SPEECH_EXCLUDE_ATTRIBUTE };
