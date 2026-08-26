/* SoAI - Shared frontend syntax highlighter render [frontend/assets/ts/core/syntaxhighlighter/render.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolve, resolveAll } from '@core/dom/dom.ts';
import { requireDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { getLanguageDefinition, normalizeLanguageId, resolveGrammar, resolveLanguageLabel, resolvePresentedLanguage } from '@core/syntaxhighlighter/service.ts';
import { collectTokens, sanitizeTokenType } from '@core/syntaxhighlighter/tokenization.ts';
import type { HighlightOptions, Token } from '@core/syntaxhighlighter/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isInstanceOf, isString } from '@core/typeGuards.ts';

const renderTokens = (documentRef: Document, content: JsonValue | null | undefined, tokens: Token[] | null): DocumentFragment => {
    const fragment = documentRef.createDocumentFragment();
    const text = isString(content) ? content : '';
    const tokenList = tokens && isArray(tokens) ? tokens : [];
    if (tokenList.length === 0) {
        if (text) {
            fragment.appendChild(documentRef.createTextNode(text));
        }
        return fragment;
    }
    let cursor = 0;
    tokenList.forEach((token) => {
        const rawStart = Number.isFinite(token?.start) ? token.start : 0;
        const rawEnd = Number.isFinite(token?.end) ? token.end : rawStart;
        const start = clampNumber(rawStart, 0, text.length);
        const end = clampNumber(rawEnd, start, text.length);
        if (cursor < start) {
            const prefix = text.slice(cursor, start);
            if (prefix) {
                fragment.appendChild(documentRef.createTextNode(prefix));
            }
        }
        if (end > start) {
            const span = documentRef.createElement('span');
            span.className = ['token', ...sanitizeTokenType(token.type)].join(' ');
            span.textContent = text.slice(start, end);
            fragment.appendChild(span);
        }
        cursor = Math.max(cursor, end);
    });
    if (cursor < text.length) {
        const suffix = text.slice(cursor);
        if (suffix) {
            fragment.appendChild(documentRef.createTextNode(suffix));
        }
    }
    return fragment;
};

const highlight = (content: JsonValue | null | undefined, language: JsonValue | null | undefined, codeRecognitionEnabled: boolean, options: HighlightOptions = {}): HTMLPreElement => {
    const text = isString(content) ? content.replace(/\r\n/g, '\n') : '';
    const presentedLanguage = resolvePresentedLanguage(text, language, codeRecognitionEnabled);
    const definition = getLanguageDefinition(presentedLanguage) ?? getLanguageDefinition('plaintext');
    if (!definition) {
        throw new Error('Syntax highlighter plaintext language definition is missing');
    }
    const grammar = resolveGrammar(definition);

    const documentRef = requireDocument();
    const pre = documentRef.createElement('pre');
    const defId = definition.id;
    const plainTextLabel = i18n.t('common.placeholders.plainTextCodeBlockLanguage');
    const isPlainText = defId === 'plaintext';
    const defLabel = isPlainText ? plainTextLabel : resolveLanguageLabel(definition);
    pre.className = 'code-block';
    pre.dataset['codeHighlighted'] = 'true';
    pre.setAttribute('data-language', defId);
    pre.setAttribute('data-language-label', isPlainText ? plainTextLabel : defLabel);
    pre.setAttribute('data-variant', isPlainText ? 'text' : 'code');
    if (isPlainText) {
        pre.classList.add('code-block-plain');
    }

    if (options?.className) {
        pre.classList.add(options.className);
    }

    const code = documentRef.createElement('code');
    code.className = `code language-${defId}`;
    code.setAttribute('data-language', defId);
    code.setAttribute('data-empty-placeholder', i18n.t('common.placeholders.emptyCodeBlock'));

    if (!grammar || grammar.length === 0 || defId === 'plaintext') {
        code.textContent = text;
    } else {
        const tokens = collectTokens(text, grammar);
        const fragment = renderTokens(documentRef, text, tokens);
        if (fragment.childNodes.length) {
            code.appendChild(fragment);
        }
    }

    pre.appendChild(code);

    if (options?.wrap === true) {
        pre.classList.add('code-block-wrap');
    }

    return pre;
};

const mergeAttributes = (source: Element, target: Element): void => {
    if (!source || !target) {
        return;
    }
    Array.from(source.attributes ?? []).forEach((attr) => {
        const name = attr.name;
        if (name === 'class' || name === 'data-code-highlighted' || name === 'data-language' || name === 'data-language-label') {
            return;
        }
        if (!target.hasAttribute(name)) {
            target.setAttribute(name, attr.value);
        }
    });
    const sourceClasses = Array.from(source.classList ?? []);
    sourceClasses.forEach((cls) => {
        if (!cls || target.classList.contains(cls)) {
            return;
        }
        target.classList.add(cls);
    });
    if (!target.id && source.id) {
        target.id = source.id;
    }
};

const applyHighlightedPreInPlace = (pre: HTMLPreElement, highlighted: HTMLPreElement): HTMLPreElement => {
    const scrollTop = pre.scrollTop;
    const scrollLeft = pre.scrollLeft;
    for (const attr of Array.from(pre.attributes)) {
        if (!highlighted.hasAttribute(attr.name)) {
            pre.removeAttribute(attr.name);
        }
    }
    for (const attr of Array.from(highlighted.attributes)) {
        if (pre.getAttribute(attr.name) !== attr.value) {
            pre.setAttribute(attr.name, attr.value);
        }
    }
    pre.replaceChildren(...Array.from(highlighted.childNodes).map((node) => node.cloneNode(true)));
    pre.scrollTop = scrollTop;
    pre.scrollLeft = scrollLeft;
    return pre;
};

const resolvePreElement = (element: Element): HTMLPreElement | null => {
    const htmlPreElementCtor = typeof globalThis === 'object' && globalThis ? globalThis.HTMLPreElement : undefined;
    if (element.nodeName === 'PRE') {
        return isInstanceOf(element, htmlPreElementCtor) ? element : null;
    }
    if (element.nodeName === 'CODE' && element.parentElement?.nodeName === 'PRE') {
        const parent = element.parentElement;
        return parent && isInstanceOf(parent, htmlPreElementCtor) ? parent : null;
    }
    return null;
};

const resolveElementLanguageHint = (pre: HTMLPreElement, code: HTMLElement): string | null => {
    const preLanguage = normalizeLanguageId(pre.getAttribute('data-language'));
    if (preLanguage) {
        return preLanguage;
    }
    const codeLanguage = normalizeLanguageId(code.getAttribute('data-language'));
    if (codeLanguage) {
        return codeLanguage;
    }
    return null;
};

const highlightElement = (element: Element | null, codeRecognitionEnabled: boolean, options: HighlightOptions = {}): HTMLPreElement | null => {
    if (!element) {
        return null;
    }

    const pre = resolvePreElement(element);
    if (!pre) {
        return null;
    }

    if (pre.dataset['codeHighlighted'] === 'true' && options.force !== true) {
        return pre;
    }

    const codeCandidate = resolve('code', pre);
    const code = codeCandidate instanceof HTMLElement ? codeCandidate : pre;
    const content = code.textContent ?? '';
    const languageHint = options.language ?? resolveElementLanguageHint(pre, code);
    const highlighted = highlight(content, languageHint, codeRecognitionEnabled, options);
    mergeAttributes(pre, highlighted);
    return applyHighlightedPreInPlace(pre, highlighted);
};

const highlightAll = (container: Element | null, codeRecognitionEnabled: boolean, options: HighlightOptions = {}): HTMLPreElement[] => {
    if (!container) {
        return [];
    }
    const blocks = resolveAll('pre', container);
    return blocks.map((block) => highlightElement(block, codeRecognitionEnabled, options)).filter((element): element is HTMLPreElement => element !== null);
};

export { highlight, highlightAll, highlightElement };
