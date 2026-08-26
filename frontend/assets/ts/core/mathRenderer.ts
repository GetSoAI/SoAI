/* SoAI - Shared frontend math renderer [frontend/assets/ts/core/mathRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import katex from 'katex';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface MathRenderResult {
    processedText: string;
    hasBlockMath: boolean;
    hasInlineMath: boolean;
}

type PlaceholderCreator = (value: string) => string;

class MathRenderer {
    #sanitizer: Pick<SanitizerApi, 'html' | 'attribute'>;
    #katexOptions: katex.KatexOptions;
    #blockMathOptions: katex.KatexOptions;

    constructor(sanitizer: Pick<SanitizerApi, 'html' | 'attribute'>) {
        if (!sanitizer) {
            throw new Error('MathRenderer requires a sanitizer');
        }
        this.#sanitizer = sanitizer;
        this.#katexOptions = {
            throwOnError: false,
            errorColor: '#cc0000',
            strict: false,
            trust: false,
            output: 'html',
            displayMode: false
        };
        this.#blockMathOptions = {
            ...this.#katexOptions,
            displayMode: true
        };
    }

    processMathInText(text: string, createPlaceholder?: PlaceholderCreator): MathRenderResult {
        let processedText = text;
        let hasBlockMath = false;
        let hasInlineMath = false;

        processedText = this.#processBlockMath(processedText, createPlaceholder);
        if (processedText !== text) {
            hasBlockMath = true;
        }

        const afterBlockMath = processedText;
        processedText = this.#processInlineMath(processedText, createPlaceholder);
        if (processedText !== afterBlockMath) {
            hasInlineMath = true;
        }

        return { processedText, hasBlockMath, hasInlineMath };
    }

    #processBlockMath(text: string, createPlaceholder?: PlaceholderCreator): string {
        const blockMathPattern = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]/g;
        return text.replace(blockMathPattern, (_match, dollarContent: string, bracketContent: string) => {
            const renderedMath = this.#renderMath((dollarContent ?? bracketContent ?? '').trim(), true);
            if (!createPlaceholder) {
                return renderedMath;
            }
            return createPlaceholder(renderedMath);
        });
    }

    #processInlineMath(text: string, createPlaceholder?: PlaceholderCreator): string {
        const inlineMathPattern = /(?<!\$)\$(?!\$)(?!\s)([^\$\n]+?)(?<!\s)\$(?!\$)(?!\d)|\\\(([\s\S]*?)\\\)/g;
        return text.replace(inlineMathPattern, (_match, dollarContent: string, parenContent: string) => {
            const renderedMath = this.#renderMath((dollarContent ?? parenContent ?? '').trim(), false);
            if (!createPlaceholder) {
                return renderedMath;
            }
            return createPlaceholder(renderedMath);
        });
    }

    #renderMath(content: string, isDisplayMode: boolean): string {
        const options = isDisplayMode ? this.#blockMathOptions : this.#katexOptions;
        const containerClass = isDisplayMode ? 'math-block' : 'math-inline';
        try {
            const renderedHtml = katex.renderToString(content, options);
            return `<span class="${containerClass}">${renderedHtml}</span>`;
        } catch (error) {
            const errorMessage = ensureError(error).message;
            const normalizedError = errorMessage.replace(/\r?\n/g, ' ');
            const title = this.#sanitizer.attribute(normalizedError);
            const escapedContent = this.#sanitizer.html(content);
            return `<span class="${containerClass} math-error" data-tooltip="${title}">${escapedContent}</span>`;
        }
    }
}

export { MathRenderer };
export type { MathRenderResult };
