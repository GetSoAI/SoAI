/* SoAI - Shared frontend syntax highlighter public contracts [frontend/assets/ts/core/syntaxhighlighter/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface GrammarRule {
    type: string;
    regex: RegExp;
    priority: number;
    group?: number | undefined;
    once?: boolean | undefined;
}

interface LanguageDefinition {
    id: string;
    label: string;
    aliases: string[];
    score: (text: string, trimmed?: string) => number;
    grammar: GrammarRule[];
    extends?: string | undefined;
}

interface Token {
    start: number;
    end: number;
    type: string;
    priority: number;
}

interface ShebangInfo {
    command: string;
    inputArguments: string[];
}

interface LanguageMetadata {
    id: string;
    label: string;
    aliases: string[];
}

interface HighlightOptions {
    className?: string | undefined;
    wrap?: boolean | undefined;
    language?: string | undefined;
    force?: boolean | undefined;
}

export type { GrammarRule, HighlightOptions, LanguageDefinition, LanguageMetadata, ShebangInfo, Token };
