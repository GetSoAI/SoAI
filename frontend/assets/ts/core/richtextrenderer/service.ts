/* SoAI - Shared rich text renderer service [frontend/assets/ts/core/richtextrenderer/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MathRenderer } from '@core/mathRenderer.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { LANGUAGE_ALIASES } from '@core/richtextrenderer/constants.ts';
import { buildFootnotesSection, buildRenderBlocks, extractFootnoteDefinitions, normalizeMultilineInput } from '@core/richtextrenderer/mappers.ts';
import { processTextLines } from '@core/richtextrenderer/adapters.ts';
import { processTablesInText } from '@core/richtextrenderer/tableRendering.ts';
import type { CodeBlockDescriptor, FootnoteDefinition, RenderOptions, RichTextRendererOptions, RenderBlock, RichTextTableMode } from '@core/richtextrenderer/types.ts';
import { createPlaceholder, createPlaceholderState, type PlaceholderState, renderInlineText } from '@core/richtextrenderer/effects.ts';
import { createMermaidPlaceholder } from '@core/mermaid/placeholder.ts';
import { highlightToHtml } from '@core/syntaxhighlighter/highlightToHtml.ts';
import { resolvePresentedLanguage } from '@core/syntaxhighlighter/service.ts';

type MermaidFenceVariant = {
    isMermaid: boolean;
    diagramType: string | null;
};

const parseMermaidFenceVariant = (languageHint: string): MermaidFenceVariant => {
    const normalized = languageHint.trim().toLowerCase();
    if (!normalized) {
        return { isMermaid: false, diagramType: null };
    }
    if (normalized === 'mermaid') {
        return { isMermaid: true, diagramType: null };
    }
    if (!normalized.startsWith('mermaid')) {
        return { isMermaid: false, diagramType: null };
    }
    const suffix = normalized.slice('mermaid'.length).replace(/^[._-]+/, '');
    if (!suffix) {
        return { isMermaid: true, diagramType: null };
    }
    const token = suffix.split(/[._-]+/).filter(Boolean)[0] ?? '';
    return { isMermaid: true, diagramType: token || null };
};

const ensureMermaidTimelineDirective = (definition: string): string => {
    if (/^\s*timeline\b/i.test(definition)) {
        return definition;
    }
    return `timeline\n${definition.trimStart()}`;
};

export class RichTextRenderer {
    #sanitizer: SanitizerApi;
    #mathRenderer: MathRenderer;
    readonly #translateFootnoteBackRef: () => string;
    readonly #isCodeRecognitionEnabled: () => boolean;

    constructor(options: RichTextRendererOptions) {
        this.#sanitizer = options.sanitizer;
        this.#mathRenderer = new MathRenderer(this.#sanitizer);
        this.#translateFootnoteBackRef = options.translateFootnoteBackRef;
        this.#isCodeRecognitionEnabled = options.isCodeRecognitionEnabled;
    }

    render(content: string, options: RenderOptions = {}): string {
        if (options.tableSortAction !== undefined && (typeof options.tableSortAction !== 'string' || !options.tableSortAction.trim() || options.tableSortAction !== options.tableSortAction.trim())) {
            throw new Error('Rich-text table sort action must be a non-empty trimmed string');
        }
        const normalized = normalizeMultilineInput(content);
        if (!normalized) {
            return '<p></p>';
        }
        const footnoteResult = extractFootnoteDefinitions(normalized);
        const blocks = buildRenderBlocks(footnoteResult.processedText, (rawLanguageHint) => this.#normalizeLanguageHint(rawLanguageHint));
        const bodyHtml = blocks.map((block) => (block.type === 'code' ? this.#renderCodeBlock(block.value, block.language, options.wrapCodeBlock) : this.#renderTextBlock(block.value, footnoteResult.footnotes, options))).join('');
        const footnotesHtml = this.#buildFootnotesSection(footnoteResult.footnotes);
        return bodyHtml + footnotesHtml;
    }

    #buildFootnotesSection(footnotes: Map<string, FootnoteDefinition>): string {
        return buildFootnotesSection(
            footnotes,
            (value: string, footnotesMap: Map<string, FootnoteDefinition>) => this.#renderInlineText(value, footnotesMap),
            (value: string) => this.#escapeHtml(value),
            this.#translateFootnoteBackRef
        );
    }

    #renderTextBlock(value: string, footnotes: Map<string, FootnoteDefinition> = new Map(), options: RenderOptions = {}): string {
        const normalized = normalizeMultilineInput(value);
        if (!normalized) {
            return '<p></p>';
        }
        const placeholderState: PlaceholderState = createPlaceholderState();
        const mathResult = this.#mathRenderer.processMathInText(normalized, (renderedMath: string) => {
            return createPlaceholder(renderedMath, placeholderState.placeholders, placeholderState.placeholderIndexRef);
        });
        const inlineRenderer = (valueToRender: string): string => {
            return this.#renderInlineText(valueToRender, footnotes, placeholderState);
        };
        const withTables = processTablesInText(mathResult.processedText, inlineRenderer, {
            tableMode: options.tableMode ?? 'strict',
            tableSortAction: options.tableSortAction ?? null,
            escapeAttribute: (attributeValue) => this.#sanitizer.attribute(attributeValue)
        });
        return processTextLines(withTables, footnotes, inlineRenderer);
    }

    #renderCodeBlock(value: string, languageHint: string | null, wrapper?: (descriptor: CodeBlockDescriptor) => string): string {
        const normalized = normalizeMultilineInput(value);
        const language = languageHint && languageHint.length > 0 ? languageHint : null;

        if (language) {
            const variant = parseMermaidFenceVariant(language);
            if (variant.isMermaid) {
                const definition = variant.diagramType === 'timeline' ? ensureMermaidTimelineDirective(normalized) : normalized;
                return createMermaidPlaceholder(definition);
            }
        }

        const codeRecognitionEnabled = this.#isCodeRecognitionEnabled();
        const presentedLanguage = resolvePresentedLanguage(normalized, language, codeRecognitionEnabled);
        const html = highlightToHtml(normalized, presentedLanguage, codeRecognitionEnabled);
        if (wrapper) {
            return wrapper({
                html,
                language: presentedLanguage,
                value: normalized
            });
        }
        return html;
    }

    #renderInlineText(value: string, footnotes: Map<string, FootnoteDefinition> = new Map(), placeholderState?: PlaceholderState): string {
        return renderInlineText(
            value,
            footnotes,
            {
                escapeHtml: (valueToEscape: string) => this.#escapeHtml(valueToEscape),
                sanitizeUrl: (url: string) => this.#sanitizer.url(url),
                sanitizeImage: (url: string) => this.#sanitizer.image(url)
            },
            placeholderState
        );
    }

    #normalizeLanguageHint(raw: string | undefined | null): string | null {
        if (!raw) {
            return null;
        }
        const trimmed = raw.trim();
        if (!trimmed) {
            return null;
        }
        const prefixSanitized = trimmed.replace(/^(?:lang(?:uage)?\s*=)/i, '').trim();
        const candidate = prefixSanitized || trimmed;
        const token = candidate.split(/[\s,;|]+/).filter(Boolean)[0] ?? '';
        let hint = token;
        if (hint.startsWith('file:')) {
            hint = hint.slice(5);
        }
        if (hint.includes('/')) {
            hint = hint.split('/').pop() ?? hint;
        }
        if (hint.includes('\\')) {
            hint = hint.split('\\').pop() ?? hint;
        }
        const extension = hint.includes('.') ? (hint.split('.').pop() ?? hint) : hint;
        const normalized = extension.replace(/[^a-z0-9#+._-]/gi, '').toLowerCase();
        if (!normalized) {
            return null;
        }
        return LANGUAGE_ALIASES[normalized] ?? normalized;
    }

    #escapeHtml(value: string): string {
        return this.#sanitizer.html(value);
    }
}

export type { RenderOptions, RichTextRendererOptions, RenderBlock, CodeBlockDescriptor, RichTextTableMode };
