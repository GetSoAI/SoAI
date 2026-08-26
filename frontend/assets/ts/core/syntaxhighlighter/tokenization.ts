/* SoAI - Shared syntax token collection [frontend/assets/ts/core/syntaxhighlighter/tokenization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { safeCloneRegex } from '@core/syntaxhighlighter/regex.ts';
import type { GrammarRule, Token } from '@core/syntaxhighlighter/types.ts';
import { isArray, isNumber } from '@core/typeGuards.ts';

const sanitizeTokenType = (value: string): string[] => {
    if (!value) {
        return [];
    }
    return String(value)
        .split('.')
        .map((segment) => segment.trim().toLowerCase())
        .filter(Boolean)
        .map((segment) => `token-${segment}`);
};

const advanceZeroWidthMatch = (regex: RegExp, matchIndex: number): void => {
    if (regex.lastIndex === matchIndex) {
        regex.lastIndex += 1;
    }
};

const collectTokens = (content: string, grammar: GrammarRule[]): Token[] => {
    if (!grammar || !isArray(grammar) || grammar.length === 0) {
        return [];
    }
    const tokens: Token[] = [];

    grammar.forEach((rule) => {
        if (!rule?.regex) {
            return;
        }
        const regex = safeCloneRegex(rule.regex);
        let match: RegExpExecArray | null;
        let guard = 0;
        while ((match = regex.exec(content)) !== null) {
            guard += 1;
            if (guard > 6000) {
                break;
            }

            let value = match[0];
            let startIndex = match.index;

            if (isNumber(rule.group) && rule.group >= 0) {
                const groupValue = match[rule.group];
                if (!groupValue) {
                    advanceZeroWidthMatch(regex, match.index);
                    continue;
                }
                const offset = value.indexOf(groupValue);
                if (offset < 0) {
                    advanceZeroWidthMatch(regex, match.index);
                    continue;
                }
                startIndex = match.index + offset;
                value = groupValue;
            }

            const endIndex = startIndex + value.length;
            if (endIndex <= startIndex) {
                advanceZeroWidthMatch(regex, match.index);
                continue;
            }

            tokens.push({
                start: startIndex,
                end: endIndex,
                type: rule.type ?? '',
                priority: Number.isFinite(rule.priority) ? rule.priority : 0
            });

            if (rule.once) {
                break;
            }

            advanceZeroWidthMatch(regex, match.index);
        }
    });

    tokens.sort((firstValue, secondValue) => {
        if (firstValue.start !== secondValue.start) {
            return firstValue.start - secondValue.start;
        }
        if (firstValue.priority !== secondValue.priority) {
            return secondValue.priority - firstValue.priority;
        }
        const aLength = firstValue.end - firstValue.start;
        const bLength = secondValue.end - secondValue.start;
        return bLength - aLength;
    });

    const filtered: Token[] = [];
    let cursor = -1;
    tokens.forEach((token) => {
        if (token.start >= cursor) {
            filtered.push(token);
            cursor = token.end;
        }
    });

    return filtered;
};

export { collectTokens, sanitizeTokenType };
