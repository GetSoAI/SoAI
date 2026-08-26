/* SoAI - Shared rich text renderer contracts [frontend/assets/ts/core/richtextrenderer/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';

export interface RichTextRendererOptions {
    sanitizer: SanitizerApi;
    translateFootnoteBackRef: () => string;
    isCodeRecognitionEnabled: () => boolean;
}

interface TextRenderBlock {
    type: 'text';
    value: string;
}

interface CodeRenderBlock {
    type: 'code';
    value: string;
    language: string | null;
}

export type RenderBlock = TextRenderBlock | CodeRenderBlock;

export interface CodeBlockDescriptor {
    html: string;
    language: string | null;
    value: string;
}

export type RichTextTableMode = 'strict' | 'streaming';

export interface RenderOptions {
    wrapCodeBlock?: (descriptor: CodeBlockDescriptor) => string;
    tableMode?: RichTextTableMode;
    tableSortAction?: string;
}

export interface FootnoteDefinition {
    id: string;
    content: string;
}

export interface FootnoteProcessResult {
    processedText: string;
    footnotes: Map<string, FootnoteDefinition>;
}

export interface InlineRenderDependencies {
    escapeHtml: (value: string) => string;
    sanitizeUrl: (url: string) => string | null;
    sanitizeImage: (url: string) => string | null;
}
