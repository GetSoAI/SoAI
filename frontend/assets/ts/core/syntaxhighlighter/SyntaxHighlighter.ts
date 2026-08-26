/* SoAI - Shared frontend syntax highlighter implementation [frontend/assets/ts/core/syntaxhighlighter/SyntaxHighlighter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLanguageDefinition, listLanguages, resolveLanguageLabel, resolvePresentedLanguage } from '@core/syntaxhighlighter/service.ts';
import { highlight, highlightAll, highlightElement } from '@core/syntaxhighlighter/render.ts';
import type { HighlightOptions, LanguageDefinition, LanguageMetadata } from '@core/syntaxhighlighter/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';

class SyntaxHighlighter {
    readonly #isCodeRecognitionEnabled: () => boolean;

    constructor(isCodeRecognitionEnabled: () => boolean) {
        this.#isCodeRecognitionEnabled = isCodeRecognitionEnabled;
    }

    detectLanguage(content: string): string {
        return resolvePresentedLanguage(content, null, this.#isCodeRecognitionEnabled());
    }

    highlight(content: JsonValue | null | undefined, language: JsonValue | null | undefined, options: HighlightOptions = {}): HTMLPreElement {
        return highlight(content, language, this.#isCodeRecognitionEnabled(), options);
    }

    highlightElement(element: Element | null, options: HighlightOptions = {}): HTMLPreElement | null {
        return highlightElement(element, this.#isCodeRecognitionEnabled(), options);
    }

    highlightAll(container: Element | null, options: HighlightOptions = {}): HTMLPreElement[] {
        return highlightAll(container, this.#isCodeRecognitionEnabled(), options);
    }

    listLanguages(): LanguageMetadata[] {
        return listLanguages();
    }

    getLanguageMetadata(language: JsonValue | null | undefined): LanguageMetadata | null {
        const definition: LanguageDefinition | null = getLanguageDefinition(language);
        if (!definition) {
            return null;
        }
        return {
            id: definition.id,
            label: resolveLanguageLabel(definition),
            aliases: isArray(definition.aliases) ? [...definition.aliases] : []
        };
    }
}

export { SyntaxHighlighter };
