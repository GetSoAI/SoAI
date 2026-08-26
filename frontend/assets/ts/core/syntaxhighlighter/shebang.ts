/* SoAI - Shared frontend syntax highlighter shebang [frontend/assets/ts/core/syntaxhighlighter/shebang.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ShebangInfo } from '@core/syntaxhighlighter/types.ts';
import { isString } from '@core/typeGuards.ts';

const SHEBANG_LANGUAGE_ALIASES: Map<string, string> = new Map([
    ['bash', 'bash'],
    ['sh', 'bash'],
    ['zsh', 'bash'],
    ['ksh', 'bash'],
    ['dash', 'bash'],
    ['ash', 'bash'],
    ['fish', 'bash'],
    ['php', 'php'],
    ['python', 'python'],
    ['python2', 'python'],
    ['python3', 'python'],
    ['pypy', 'python'],
    ['node', 'javascript'],
    ['bun', 'javascript'],
    ['deno', 'javascript'],
    ['ts-node', 'typescript'],
    ['tsx', 'typescript']
]);

const parseShebang = (content: string): ShebangInfo | null => {
    if (!isString(content) || !content.startsWith('#!')) {
        return null;
    }
    const endIndex = content.indexOf('\n');
    const firstLine = endIndex >= 0 ? content.slice(0, endIndex) : content;
    const raw = firstLine.slice(2).trim();
    if (!raw) {
        return null;
    }
    const tokens = raw.split(/\s+/).filter(Boolean);
    if (tokens.length === 0) {
        return null;
    }
    const command = tokens[0];
    let inputArguments = tokens.slice(1);

    const commandName = (value: string | undefined): string => {
        if (!value) return '';
        const normalized = value.replace(/^[^\w]*|[^\w]*$/g, '');
        const parts = normalized.split('/').filter(Boolean);
        return parts.length > 0 ? (parts[parts.length - 1] ?? normalized) : normalized;
    };

    let cli = commandName(command);

    if (cli === 'env') {
        const nonFlag = inputArguments.find((token) => !token.startsWith('-'));
        cli = commandName(nonFlag);
        inputArguments = inputArguments.slice(inputArguments.indexOf(nonFlag ?? '') + 1);
    }

    if (!cli) {
        return null;
    }

    return {
        command: cli.toLowerCase(),
        inputArguments: inputArguments.map((argument) => commandName(argument).toLowerCase())
    };
};

const detectShebangLanguage = (trimmed: string): string | null => {
    if (!trimmed.startsWith('#!')) {
        return null;
    }
    const info = parseShebang(trimmed);
    if (!info?.command) {
        return null;
    }

    if (SHEBANG_LANGUAGE_ALIASES.has(info.command)) {
        return SHEBANG_LANGUAGE_ALIASES.get(info.command) ?? null;
    }

    const inferFromArguments = info.inputArguments.find((argument) => SHEBANG_LANGUAGE_ALIASES.has(argument));
    if (inferFromArguments) {
        return SHEBANG_LANGUAGE_ALIASES.get(inferFromArguments) ?? null;
    }

    if (info.command.startsWith('python')) {
        return 'python';
    }
    if (info.command.includes('node') || info.command.includes('deno') || info.command.includes('bun')) {
        return 'javascript';
    }
    if (info.command.includes('ts-node') || info.command.includes('tsx')) {
        return 'typescript';
    }

    return null;
};

export { detectShebangLanguage };
