/* SoAI - Frontend syntax highlighter registry [frontend/assets/ts/core/syntaxhighlighter/syntaxHighlighterRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SyntaxHighlighter } from '@core/syntaxhighlighter/SyntaxHighlighter.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import type { GrammarRule, HighlightOptions, LanguageDefinition, LanguageMetadata, ShebangInfo, Token } from '@core/syntaxhighlighter/types.ts';

const SYNTAX_HIGHLIGHTER_SERVICE_ID = 'core.syntaxHighlighter';

const requireSyntaxHighlighter = (): SyntaxHighlighter => {
    const candidate = resolveKernelService(SYNTAX_HIGHLIGHTER_SERVICE_ID);
    if (!(candidate instanceof SyntaxHighlighter)) {
        throw new Error(`${SYNTAX_HIGHLIGHTER_SERVICE_ID} is not registered`);
    }
    return candidate;
};

export { SYNTAX_HIGHLIGHTER_SERVICE_ID, SyntaxHighlighter, requireSyntaxHighlighter };
export type { GrammarRule, HighlightOptions, LanguageDefinition, LanguageMetadata, ShebangInfo, Token };
