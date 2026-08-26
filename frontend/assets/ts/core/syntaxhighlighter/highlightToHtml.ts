/* SoAI - DOM-free syntax highlighting to HTML strings [frontend/assets/ts/core/syntaxhighlighter/highlightToHtml.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { escapeHtml } from '@core/security/textSanitizer.ts';
import { getLanguageDefinition, resolveGrammar, resolveLanguageLabel, resolvePresentedLanguage } from '@core/syntaxhighlighter/service.ts';
import { collectTokens, sanitizeTokenType } from '@core/syntaxhighlighter/tokenization.ts';
import type { HighlightOptions, Token } from '@core/syntaxhighlighter/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

const renderTokenizedHtml = (content: string, tokens: Token[]): string => {
    if (tokens.length === 0) {
        return escapeHtml(content);
    }
    const parts: string[] = [];
    let cursor = 0;
    for (const token of tokens) {
        const rawStart = Number.isFinite(token?.start) ? token.start : 0;
        const rawEnd = Number.isFinite(token?.end) ? token.end : rawStart;
        const start = clampNumber(rawStart, 0, content.length);
        const end = clampNumber(rawEnd, start, content.length);

        if (cursor < start) {
            const prefix = content.slice(cursor, start);
            if (prefix) {
                parts.push(escapeHtml(prefix));
            }
        }

        if (end > start) {
            const classNames = ['token', ...sanitizeTokenType(token.type)].join(' ');
            const text = escapeHtml(content.slice(start, end));
            parts.push(`<span class="${classNames}">${text}</span>`);
        }

        cursor = Math.max(cursor, end);
    }
    if (cursor < content.length) {
        const suffix = content.slice(cursor);
        if (suffix) {
            parts.push(escapeHtml(suffix));
        }
    }
    return parts.join('');
};

const highlightToHtml = (content: JsonValue | null | undefined, language: JsonValue | null | undefined, codeRecognitionEnabled: boolean, options: HighlightOptions = {}): string => {
    const text = isString(content) ? content.replace(/\r\n/g, '\n') : '';
    const presentedLanguage = resolvePresentedLanguage(text, language, codeRecognitionEnabled);
    const definition = getLanguageDefinition(presentedLanguage) ?? getLanguageDefinition('plaintext');
    if (!definition) {
        throw new Error('Syntax highlighter plaintext language definition is missing');
    }
    const grammar = resolveGrammar(definition);

    const defId = definition.id;
    const plainTextLabel = i18n.t('common.placeholders.plainTextCodeBlockLanguage');
    const isPlainText = defId === 'plaintext';
    const defLabel = isPlainText ? plainTextLabel : resolveLanguageLabel(definition);
    const variant = isPlainText ? 'text' : 'code';

    const classNames: string[] = ['code-block'];
    if (isPlainText) {
        classNames.push('code-block-plain');
    }
    if (options?.className) {
        classNames.push(options.className);
    }
    if (options?.wrap === true) {
        classNames.push('code-block-wrap');
    }

    const languageLabel = isPlainText ? plainTextLabel : defLabel;
    const codeClassName = `code language-${defId}`;
    const codeHtml = !grammar || grammar.length === 0 || defId === 'plaintext' ? escapeHtml(text) : renderTokenizedHtml(text, collectTokens(text, grammar));
    const emptyPlaceholder = escapeHtml(i18n.t('common.placeholders.emptyCodeBlock'));

    return `<pre class="${classNames.join(' ')}" data-code-highlighted="true" data-language="${escapeHtml(defId)}" data-language-label="${escapeHtml(languageLabel)}" data-variant="${escapeHtml(variant)}"><code class="${escapeHtml(codeClassName)}" data-language="${escapeHtml(defId)}" data-empty-placeholder="${emptyPlaceholder}">${codeHtml}</code></pre>`;
};

export { highlightToHtml };
