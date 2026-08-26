/* SoAI - Shared frontend syntax highlighter service [frontend/assets/ts/core/syntaxhighlighter/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dynamicThreshold } from '@core/syntaxhighlighter/scoring/public.ts';
import { detectShebangLanguage } from '@core/syntaxhighlighter/shebang.ts';
import { i18n } from '@core/i18n/index.ts';
import type { SyntaxHighlighterLanguagesTranslationKey } from '@core/i18n/translationkeys/syntaxhighlighter/languages.generated.ts';
import type { GrammarRule, LanguageDefinition, LanguageMetadata } from '@core/syntaxhighlighter/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import { LANGUAGE_BY_ALIAS, LANGUAGE_BY_ID, LANGUAGE_DEFINITIONS } from '@core/syntaxhighlighter/state.ts';

const normalizeLanguageId = (language: JsonValue | null | undefined): string | null => {
    if (!language) {
        return null;
    }
    const value = String(language).toLowerCase();
    if (LANGUAGE_BY_ID.has(value)) {
        return value;
    }
    if (LANGUAGE_BY_ALIAS.has(value)) {
        return LANGUAGE_BY_ALIAS.get(value) ?? null;
    }
    return null;
};

const getLanguageDefinition = (language: JsonValue | null | undefined): LanguageDefinition | null => {
    if (!language) {
        return null;
    }
    const normalized = normalizeLanguageId(language);
    if (!normalized) {
        return null;
    }
    return LANGUAGE_BY_ID.get(normalized) ?? null;
};

const resolveLanguageLabel = (definition: LanguageDefinition): string => {
    switch (definition.id) {
        case 'javascript':
            return i18n.t('syntaxHighlighter.languages.javascript');
        case 'typescript':
            return i18n.t('syntaxHighlighter.languages.typescript');
        case 'python':
            return i18n.t('syntaxHighlighter.languages.python');
        case 'json':
            return i18n.t('syntaxHighlighter.languages.json');
        case 'yaml':
            return i18n.t('syntaxHighlighter.languages.yaml');
        case 'html':
            return i18n.t('syntaxHighlighter.languages.html');
        case 'css':
            return i18n.t('syntaxHighlighter.languages.css');
        case 'bash':
            return i18n.t('syntaxHighlighter.languages.shell');
        case 'go':
            return i18n.t('syntaxHighlighter.languages.go');
        case 'rust':
            return i18n.t('syntaxHighlighter.languages.rust');
        case 'php':
            return i18n.t('syntaxHighlighter.languages.php');
        case 'csharp':
            return i18n.t('syntaxHighlighter.languages.csharp');
        case 'xml':
            return i18n.t('syntaxHighlighter.languages.xml');
        case 'ruby':
            return i18n.t('syntaxHighlighter.languages.ruby');
        case 'java':
            return i18n.t('syntaxHighlighter.languages.java');
        case 'c':
            return i18n.t('syntaxHighlighter.languages.cCpp');
        case 'sql':
            return i18n.t('syntaxHighlighter.languages.sql');
        case 'swift':
            return i18n.t('syntaxHighlighter.languages.swift');
        case 'kotlin':
            return i18n.t('syntaxHighlighter.languages.kotlin');
        case 'dockerfile':
            return i18n.t('syntaxHighlighter.languages.dockerfile');
        case 'markdown':
            return i18n.t('syntaxHighlighter.languages.markdown');
        case 'plaintext':
            return i18n.t('syntaxHighlighter.languages.plaintext');
        case 'diff':
            return i18n.t('syntaxHighlighter.languages.diff');
    }
    throw new Error(`Unsupported syntax highlighter language "${definition.id}"`);
};

const buildSyntaxHighlighterLanguageTranslations = (): Record<SyntaxHighlighterLanguagesTranslationKey, string> => {
    return {
        'syntaxHighlighter.languages.cCpp': i18n.t('syntaxHighlighter.languages.cCpp'),
        'syntaxHighlighter.languages.csharp': i18n.t('syntaxHighlighter.languages.csharp'),
        'syntaxHighlighter.languages.css': i18n.t('syntaxHighlighter.languages.css'),
        'syntaxHighlighter.languages.diff': i18n.t('syntaxHighlighter.languages.diff'),
        'syntaxHighlighter.languages.dockerfile': i18n.t('syntaxHighlighter.languages.dockerfile'),
        'syntaxHighlighter.languages.go': i18n.t('syntaxHighlighter.languages.go'),
        'syntaxHighlighter.languages.html': i18n.t('syntaxHighlighter.languages.html'),
        'syntaxHighlighter.languages.java': i18n.t('syntaxHighlighter.languages.java'),
        'syntaxHighlighter.languages.javascript': i18n.t('syntaxHighlighter.languages.javascript'),
        'syntaxHighlighter.languages.json': i18n.t('syntaxHighlighter.languages.json'),
        'syntaxHighlighter.languages.kotlin': i18n.t('syntaxHighlighter.languages.kotlin'),
        'syntaxHighlighter.languages.markdown': i18n.t('syntaxHighlighter.languages.markdown'),
        'syntaxHighlighter.languages.php': i18n.t('syntaxHighlighter.languages.php'),
        'syntaxHighlighter.languages.plaintext': i18n.t('syntaxHighlighter.languages.plaintext'),
        'syntaxHighlighter.languages.python': i18n.t('syntaxHighlighter.languages.python'),
        'syntaxHighlighter.languages.ruby': i18n.t('syntaxHighlighter.languages.ruby'),
        'syntaxHighlighter.languages.rust': i18n.t('syntaxHighlighter.languages.rust'),
        'syntaxHighlighter.languages.shell': i18n.t('syntaxHighlighter.languages.shell'),
        'syntaxHighlighter.languages.sql': i18n.t('syntaxHighlighter.languages.sql'),
        'syntaxHighlighter.languages.swift': i18n.t('syntaxHighlighter.languages.swift'),
        'syntaxHighlighter.languages.typescript': i18n.t('syntaxHighlighter.languages.typescript'),
        'syntaxHighlighter.languages.xml': i18n.t('syntaxHighlighter.languages.xml'),
        'syntaxHighlighter.languages.yaml': i18n.t('syntaxHighlighter.languages.yaml')
    };
};

const resolveGrammar = (definition: LanguageDefinition | null, visited: Set<string> = new Set<string>()): GrammarRule[] => {
    if (!definition || visited.has(definition.id)) {
        return [];
    }
    visited.add(definition.id);

    const ownGrammar = isArray(definition.grammar) ? definition.grammar : [];
    if (!definition.extends) {
        return ownGrammar;
    }

    const parent = getLanguageDefinition(definition.extends);
    const parentGrammar = resolveGrammar(parent, visited);
    return parentGrammar.concat(ownGrammar);
};

const detectLanguage = (content: string): string => {
    const text = content.replace(/\r\n/g, '\n');
    const trimmed = text.trim();
    if (!trimmed) {
        return 'plaintext';
    }

    const shebangLanguage = detectShebangLanguage(trimmed);
    if (shebangLanguage) {
        return shebangLanguage;
    }

    const scores: Map<string, number> = new Map<string, number>();
    let bestLanguage = 'plaintext';
    let bestScore = 0;

    LANGUAGE_DEFINITIONS.forEach((definition) => {
        if (definition.id === 'plaintext') {
            return;
        }
        const score = definition.score(text, trimmed) || 0;
        scores.set(definition.id, score);
        if (score > bestScore) {
            bestScore = score;
            bestLanguage = definition.id;
        }
    });

    const threshold = dynamicThreshold(trimmed.length);
    if (bestScore < threshold) {
        return 'plaintext';
    }
    if (bestLanguage === 'typescript') {
        const tsScore = scores.get('typescript') ?? 0;
        const jsScore = scores.get('javascript') ?? 0;
        if (tsScore - jsScore <= 0) {
            return 'javascript';
        }
    }

    return bestLanguage;
};

const detectDiffLanguage = (content: string): string => {
    const text = content.replace(/\r\n/g, '\n');
    const trimmed = text.trim();
    if (!trimmed) {
        return 'plaintext';
    }
    const definition = getLanguageDefinition('diff');
    if (!definition) {
        throw new Error('Syntax highlighter diff language definition is missing');
    }
    const score = definition.score(text, trimmed) || 0;
    return score >= dynamicThreshold(trimmed.length) ? 'diff' : 'plaintext';
};

const resolvePresentedLanguage = (content: string, language: JsonValue | null | undefined, codeRecognitionEnabled: boolean): string => {
    const explicitLanguage = language !== null && language !== undefined && String(language).trim().length > 0;
    const normalizedLanguage = normalizeLanguageId(language);
    if (codeRecognitionEnabled) {
        return normalizedLanguage ?? detectLanguage(content);
    }
    if (normalizedLanguage === 'diff') {
        return 'diff';
    }
    if (explicitLanguage) {
        return 'plaintext';
    }
    return detectDiffLanguage(content);
};

const listLanguages = (): LanguageMetadata[] => {
    return LANGUAGE_DEFINITIONS.filter((definition) => definition.id !== 'plaintext').map((definition) => ({
        id: definition.id,
        label: resolveLanguageLabel(definition),
        aliases: isArray(definition.aliases) ? [...definition.aliases] : []
    }));
};

export { buildSyntaxHighlighterLanguageTranslations, detectLanguage, getLanguageDefinition, listLanguages, normalizeLanguageId, resolveGrammar, resolveLanguageLabel, resolvePresentedLanguage };
