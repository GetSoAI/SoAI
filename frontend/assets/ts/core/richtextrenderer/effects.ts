/* SoAI - Shared rich text renderer effects [frontend/assets/ts/core/richtextrenderer/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FootnoteDefinition, InlineRenderDependencies } from '@core/richtextrenderer/types.ts';

const PLACEHOLDER_PREFIX = '\uE000SOAI_PH_';
const PLACEHOLDER_SUFFIX = '\uE001';
const PLACEHOLDER_PATTERN = /\uE000SOAI_PH_\d+\uE001/g;

interface PlaceholderState {
    placeholders: Map<string, string>;
    placeholderIndexRef: { value: number };
}

type MarkdownDestinationRenderer = (label: string, destination: string) => string;

const replaceMarkdownDestinations = (text: string, type: 'image' | 'link', render: MarkdownDestinationRenderer): string => {
    const openingPattern = type === 'image' ? /!\[([^\]]*)\]\(/g : /(?<!!)\[([^\]]+)\]\(/g;
    let output = '';
    let sourceOffset = 0;
    let match = openingPattern.exec(text);
    while (match) {
        const labelStart = type === 'image' ? 2 : 1;
        const label = match[0].slice(labelStart, -2);
        const destinationStart = openingPattern.lastIndex;
        let destinationEnd = -1;
        let parenthesisDepth = 1;
        let escaped = false;
        for (let characterIndex = destinationStart; characterIndex < text.length; characterIndex += 1) {
            const character = text[characterIndex];
            if (escaped) {
                escaped = false;
                continue;
            }
            if (character === '\\') {
                escaped = true;
                continue;
            }
            if (character === '(') {
                parenthesisDepth += 1;
                continue;
            }
            if (character === ')') {
                parenthesisDepth -= 1;
                if (parenthesisDepth === 0) {
                    destinationEnd = characterIndex;
                    break;
                }
            }
        }
        if (destinationEnd === -1) break;
        output += text.slice(sourceOffset, match.index);
        output += render(label, text.slice(destinationStart, destinationEnd));
        sourceOffset = destinationEnd + 1;
        openingPattern.lastIndex = sourceOffset;
        match = openingPattern.exec(text);
    }
    return sourceOffset === 0 ? text : output + text.slice(sourceOffset);
};

export const restorePlaceholders = (text: string, placeholders: Map<string, string>): string => {
    if (placeholders.size === 0) {
        return text;
    }
    let result = text;
    const maxPasses = placeholders.size + 1;
    for (let pass = 0; pass < maxPasses; pass++) {
        const resolved = result.replace(PLACEHOLDER_PATTERN, (match) => placeholders.get(match) ?? '');
        if (resolved === result) {
            break;
        }
        result = resolved;
    }
    return result;
};

export const createPlaceholder = (html: string, placeholders: Map<string, string>, placeholderIndexRef: { value: number }): string => {
    const key = `${PLACEHOLDER_PREFIX}${placeholderIndexRef.value}${PLACEHOLDER_SUFFIX}`;
    placeholders.set(key, html);
    placeholderIndexRef.value += 1;
    return key;
};

export const createPlaceholderState = (): PlaceholderState => ({
    placeholders: new Map(),
    placeholderIndexRef: { value: 0 }
});

const replaceAngleBracketAutolinks = (text: string, createPlaceholderFunctionValue: (html: string) => string, dependencies: InlineRenderDependencies): string =>
    text.replace(/<(https?:\/\/[^>]+)>/gi, (_match, url: string) => {
        const sanitizedUrl = dependencies.sanitizeUrl(url);
        if (!sanitizedUrl) {
            return `<${dependencies.escapeHtml(url)}>`;
        }
        const escapedUrl = dependencies.escapeHtml(sanitizedUrl);
        return createPlaceholderFunctionValue(`<a href="${escapedUrl}" class="external-link-confirmation" data-href="${escapedUrl}">${escapedUrl}</a>`);
    });

const trimBareUrlTrailingPunctuation = (candidateUrl: string): string => {
    let openingParenthesisCount = 0;
    let closingParenthesisCount = 0;
    for (const character of candidateUrl) {
        if (character === '(') openingParenthesisCount += 1;
        if (character === ')') closingParenthesisCount += 1;
    }
    let urlEnd = candidateUrl.length;
    while (urlEnd > 0) {
        const trailingCharacter = candidateUrl.charAt(urlEnd - 1);
        if ('.,;:!?]}'.includes(trailingCharacter)) {
            urlEnd -= 1;
            continue;
        }
        if (trailingCharacter === ')' && closingParenthesisCount > openingParenthesisCount) {
            closingParenthesisCount -= 1;
            urlEnd -= 1;
            continue;
        }
        break;
    }
    return candidateUrl.slice(0, urlEnd);
};

const replaceBareUrls = (text: string, createPlaceholderFunctionValue: (html: string) => string, dependencies: InlineRenderDependencies): string =>
    text.replace(/(?<!["'])(https?:\/\/[^\s<>\[\]"']+)/g, (_match, candidateUrl: string) => {
        const url = trimBareUrlTrailingPunctuation(candidateUrl);
        const trailingText = candidateUrl.slice(url.length);
        const sanitizedUrl = dependencies.sanitizeUrl(url);
        if (!sanitizedUrl) {
            return dependencies.escapeHtml(candidateUrl);
        }
        const escapedUrl = dependencies.escapeHtml(sanitizedUrl);
        return `${createPlaceholderFunctionValue(`<a href="${escapedUrl}" class="external-link-confirmation" data-href="${escapedUrl}">${escapedUrl}</a>`)}${trailingText}`;
    });

export const renderInlineFormatting = (value: string, createPlaceholderFunctionValue: (html: string) => string, dependencies: InlineRenderDependencies): string => {
    let text = value;

    text = replaceMarkdownDestinations(text, 'link', (linkText, url) => {
        const sanitizedUrl = dependencies.sanitizeUrl(url);
        if (!sanitizedUrl) {
            return dependencies.escapeHtml(`[${linkText}](${url})`);
        }
        const escapedText = dependencies.escapeHtml(linkText);
        const escapedUrl = dependencies.escapeHtml(sanitizedUrl);
        const isExternalHttpUrl = /^https?:\/\//i.test(sanitizedUrl);
        if (isExternalHttpUrl) {
            return createPlaceholderFunctionValue(`<a href="${escapedUrl}" class="external-link-confirmation" data-href="${escapedUrl}">${escapedText}</a>`);
        }
        return createPlaceholderFunctionValue(`<a href="${escapedUrl}">${escapedText}</a>`);
    });

    text = replaceAngleBracketAutolinks(text, createPlaceholderFunctionValue, dependencies);
    text = replaceBareUrls(text, createPlaceholderFunctionValue, dependencies);

    return text;
};

export const renderInlineText = (value: string, footnotes: Map<string, FootnoteDefinition> = new Map(), dependencies: InlineRenderDependencies, placeholderState?: PlaceholderState): string => {
    const state = placeholderState ?? createPlaceholderState();
    const createPlaceholderFunctionValue = (html: string): string => createPlaceholder(html, state.placeholders, state.placeholderIndexRef);

    let text = value;

    text = text.replace(/`([^`]+)`/g, (_match, code: string) => {
        return createPlaceholderFunctionValue(`<code>${dependencies.escapeHtml(code)}</code>`);
    });

    text = replaceMarkdownDestinations(text, 'image', (altText, imageUrl) => {
        const sanitizedUrl = dependencies.sanitizeImage(imageUrl);
        if (!sanitizedUrl) {
            return '';
        }
        const escapedAlt = dependencies.escapeHtml(altText);
        const escapedUrl = dependencies.escapeHtml(sanitizedUrl);
        return createPlaceholderFunctionValue(`<img src="${escapedUrl}" alt="${escapedAlt}" class="markdown-image" loading="lazy">`);
    });

    text = text.replace(/\[\^([^\]]+)\]/g, (_match, footnoteId: string) => {
        const escapedId = dependencies.escapeHtml(footnoteId);
        const footnoteContent = footnotes.has(footnoteId) ? footnotes.get(footnoteId)?.content : '';
        const tooltipAttr = footnoteContent ? ` data-tooltip="${dependencies.escapeHtml(footnoteContent)}"` : '';
        return createPlaceholderFunctionValue(`<sup class="footnote-ref"><a id="fnref-${escapedId}" href="#fn-${escapedId}"${tooltipAttr}>[${escapedId}]</a></sup>`);
    });

    text = replaceMarkdownDestinations(text, 'link', (linkText, url) => {
        const sanitizedUrl = dependencies.sanitizeUrl(url);
        if (!sanitizedUrl) {
            return dependencies.escapeHtml(`[${linkText}](${url})`);
        }
        const escapedText = dependencies.escapeHtml(linkText);
        const escapedUrl = dependencies.escapeHtml(sanitizedUrl);
        const isExternalHttpUrl = /^https?:\/\//i.test(sanitizedUrl);
        if (isExternalHttpUrl) {
            return createPlaceholderFunctionValue(`<a href="${escapedUrl}" class="external-link-confirmation" data-href="${escapedUrl}">${escapedText}</a>`);
        }
        return createPlaceholderFunctionValue(`<a href="${escapedUrl}">${escapedText}</a>`);
    });

    text = text.replace(/<br\s*\/?>/gi, () => createPlaceholderFunctionValue('<br>'));
    text = replaceAngleBracketAutolinks(text, createPlaceholderFunctionValue, dependencies);

    text = text.replace(/\*\*([^*]+)\*\*/g, (_match, content: string) => {
        const rendered = renderInlineFormatting(content, createPlaceholderFunctionValue, dependencies);
        return createPlaceholderFunctionValue(`<strong>${rendered}</strong>`);
    });

    text = text.replace(/(?<!\*)\*([^*\s][^*\n]*)\*(?!\*)/g, (_match, content: string) => {
        const rendered = renderInlineFormatting(content, createPlaceholderFunctionValue, dependencies);
        return createPlaceholderFunctionValue(`<em>${rendered}</em>`);
    });

    text = text.replace(/~~([^~]+)~~/g, (_match, content: string) => {
        return createPlaceholderFunctionValue(`<del>${dependencies.escapeHtml(content)}</del>`);
    });

    text = replaceBareUrls(text, createPlaceholderFunctionValue, dependencies);

    return restorePlaceholders(dependencies.escapeHtml(text), state.placeholders).replace(/\n/g, '<br>');
};

export type { PlaceholderState };
