/* SoAI - Shared frontend syntax highlighter constants [frontend/assets/ts/core/syntaxhighlighter/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scoreBash, scoreCss, scoreGo, scoreHtml, scoreJavascript, scoreJson, scorePython, scoreRust, scoreTypescript, scoreYaml } from '@core/syntaxhighlighter/scoring/public.ts';
import { DIFF_LANGUAGE_DEFINITION } from '@core/syntaxhighlighter/languages/diff.ts';
import type { LanguageDefinition } from '@core/syntaxhighlighter/types.ts';

const PRIMARY_LANGUAGE_DEFINITIONS: LanguageDefinition[] = [
    {
        id: 'javascript',
        label: '',
        aliases: ['js', 'jsx', 'mjs', 'cjs', 'node', 'es6'],
        score: (text: string): number => scoreJavascript(text),
        grammar: [
            { type: 'comment', regex: /\/\*[\s\S]*?\*\//g, priority: 10 },
            { type: 'comment', regex: /\/\/[^\n]*/g, priority: 10 },
            { type: 'string', regex: /`(?:\\.|[^`])*`/g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 9 },
            { type: 'string', regex: /'(?:\\.|[^'\\])*'/g, priority: 9 },
            { type: 'regex', regex: /\/(?!\/)(?:\\.|[^/\n])+\/[gimsuy]*/g, priority: 8 },
            { type: 'number', regex: /\b0x[0-9a-fA-F]+\b|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g, priority: 7 },
            {
                type: 'keyword',
                regex: /\b(?:await|break|case|catch|class|const|continue|debugger|default|delete|do|else|enum|export|extends|finally|for|function|if|import|in|instanceof|let|new|null|return|super|switch|this|throw|try|typeof|var|void|while|with|yield|async|implements|interface|package|private|protected|public|static|get|set|of)\b/g,
                priority: 6
            },
            { type: 'boolean', regex: /\b(?:true|false|undefined|NaN|Infinity)\b/g, priority: 5 },
            {
                type: 'builtin',
                regex: /\b(?:Array|Date|Math|Number|Object|String|Promise|console|window|document|Set|Map|WeakMap|WeakSet|Symbol|BigInt|JSON)\b/g,
                priority: 5
            },
            { type: 'operator', regex: /[+\-*/%=<>!|&^~?:]+/g, priority: 2 },
            { type: 'punctuation', regex: /[[\]{};(),.]/g, priority: 1 }
        ]
    },
    {
        id: 'typescript',
        label: '',
        aliases: ['ts', 'tsx'],
        score: (text: string): number => scoreTypescript(text),
        extends: 'javascript',
        grammar: [
            { type: 'type', regex: /\b(?:interface|type|enum)\b/g, priority: 6 },
            { type: 'type-annotation', regex: /:\s*[A-Za-z_][\w.<>,\s]*/g, priority: 5 },
            { type: 'generic', regex: /<[A-Za-z_][\w.,\s?<=]*>/g, priority: 4 }
        ]
    },
    {
        id: 'python',
        label: '',
        aliases: ['py'],
        score: (text: string): number => scorePython(text),
        grammar: [
            { type: 'comment', regex: /#[^\n]*/g, priority: 10 },
            { type: 'string', regex: /(\"\"\"|''')[\s\S]*?\1/g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 9 },
            { type: 'string', regex: /'(?:\\.|[^'\\])*'/g, priority: 9 },
            { type: 'decorator', regex: /@[A-Za-z_][\w.]*/g, priority: 8 },
            {
                type: 'keyword',
                regex: /\b(?:and|a\x73|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b/g,
                priority: 7
            },
            {
                type: 'builtin',
                regex: /\b(?:print|len|range|dict|list|set|tuple|str|int|float|bool|super|self|enumerate|zip|map|filter|open)\b/g,
                priority: 6
            },
            { type: 'number', regex: /\b0x[0-9a-fA-F]+\b|\b\d+(?:_\d+)*(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g, priority: 5 },
            { type: 'operator', regex: /[+\-*/%=<>!|&^~]+/g, priority: 2 },
            { type: 'punctuation', regex: /[[\]{}();,.:]/g, priority: 1 }
        ]
    },
    {
        id: 'json',
        label: '',
        aliases: [],
        score: (text: string, trimmed?: string): number => scoreJson(text, trimmed ?? text.trim()),
        grammar: [
            { type: 'key', regex: /\"([^\"\\]|\\.)*\"(?=\s*:)/g, priority: 9 },
            { type: 'string', regex: /\"([^\"\\]|\\.)*\"/g, priority: 8 },
            { type: 'number', regex: /\b-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g, priority: 7 },
            { type: 'boolean', regex: /\b(?:true|false)\b/g, priority: 6 },
            { type: 'constant', regex: /\bnull\b/g, priority: 6 },
            { type: 'punctuation', regex: /[[\]{},:]/g, priority: 2 }
        ]
    },
    {
        id: 'yaml',
        label: '',
        aliases: ['yml'],
        score: (text: string, trimmed?: string): number => scoreYaml(text, trimmed ?? text.trim()),
        grammar: [
            { type: 'comment', regex: /#[^\n]*/g, priority: 8 },
            { type: 'key', regex: /^\s*[\w.+-]+\s*:/gm, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, priority: 7 },
            { type: 'number', regex: /\b-?(?:0|[1-9]\d*)(?:\.\d+)?\b/g, priority: 6 },
            { type: 'boolean', regex: /\b(?:true|false|null|yes|no|on|off)\b/gi, priority: 6 },
            { type: 'anchor', regex: /&[A-Za-z0-9_-]+|\*[A-Za-z0-9_-]+/g, priority: 6 },
            { type: 'punctuation', regex: /[[\]{}:,-]/g, priority: 2 }
        ]
    },
    {
        id: 'html',
        label: '',
        aliases: ['htm'],
        score: (text: string, trimmed?: string): number => scoreHtml(text, trimmed ?? text.trim()),
        grammar: [
            { type: 'comment', regex: /<!--[\s\S]*?-->/g, priority: 10 },
            { type: 'doctype', regex: /<!DOCTYPE[^>]*>/gi, priority: 9 },
            { type: 'tag', regex: /<\/?[A-Za-z][A-Za-z0-9:-]*/g, priority: 8 },
            { type: 'attr-name', regex: /(?:\s+)([A-Za-z_:][A-Za-z0-9:._-]*)(?=\s*=)/g, priority: 7, group: 1 },
            { type: 'attr-value', regex: /=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/g, priority: 7 },
            { type: 'entity', regex: /&[a-zA-Z]+;/g, priority: 5 }
        ]
    },
    {
        id: 'css',
        label: '',
        aliases: [],
        score: (text: string): number => scoreCss(text),
        grammar: [
            { type: 'comment', regex: /\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'selector', regex: /^[^{@][^{]*?(?=\s*\{)/gm, priority: 8 },
            { type: 'property', regex: /([\w-]+)(?=\s*:)/g, priority: 7, group: 1 },
            { type: 'value', regex: /:(?:[^;{}]+)/g, priority: 6 },
            { type: 'number', regex: /\b\d+(?:\.\d+)?(?:px|em|rem|vh|vw|%)?\b/g, priority: 6 },
            { type: 'color', regex: /#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/g, priority: 6 },
            { type: 'punctuation', regex: /[{}:;(),.]/g, priority: 2 }
        ]
    },
    {
        id: 'bash',
        label: '',
        aliases: ['sh', 'shell', 'zsh', 'bash'],
        score: (text: string, trimmed?: string): number => scoreBash(text, trimmed ?? text.trim()),
        grammar: [
            { type: 'comment', regex: /#[^\n]*/g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, priority: 8 },
            { type: 'variable', regex: /\$[\w{}@*#?[\]-]+/g, priority: 7 },
            {
                type: 'keyword',
                regex: /\b(?:if|then|fi|else|elif|for|while|do|done|case|esac|function|select|in|until|echo|read|export|local|return)\b/g,
                priority: 7
            },
            { type: 'command', regex: /^(?:\s*)([A-Za-z0-9_.-]+)(?=\s)/gm, priority: 5, group: 1 },
            { type: 'punctuation', regex: /[{}[\];(),]|&&|\|\|/g, priority: 2 }
        ]
    },
    {
        id: 'go',
        label: '',
        aliases: ['golang'],
        score: (text: string): number => scoreGo(text),
        grammar: [
            { type: 'comment', regex: /\/\/[^\n]*|\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /`[^`]*`/g, priority: 8 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 8 },
            {
                type: 'keyword',
                regex: /\b(?:break|default|func|interface|select|case|defer|go|map|struct|chan|else|goto|package|switch|const|fallthrough|if|range|type|continue|for|import|return|var)\b/g,
                priority: 7
            },
            {
                type: 'builtin',
                regex: /\b(?:fmt|append|len|cap|new|make|copy|delete|complex|real|imag|panic|recover|close)\b/g,
                priority: 6
            },
            { type: 'number', regex: /\b0x[0-9a-fA-F]+\b|\b\d+(?:\.\d+)?\b/g, priority: 5 }
        ]
    },
    {
        id: 'rust',
        label: '',
        aliases: [],
        score: (text: string): number => scoreRust(text),
        grammar: [
            { type: 'comment', regex: /\/\/\/?[^\n]*|\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 8 },
            { type: 'macro', regex: /\b[A-Za-z_][\w]*!/g, priority: 7 },
            { type: 'lifetime', regex: /'\w+/g, priority: 7 },
            {
                type: 'keyword',
                regex: /\b(?:a\x73|break|const|continue|crate|else|enum|extern|false|fn|for|if|impl|in|let|loop|match|mod|move|mut|pub|ref|return|self|Self|static|struct|super|trait|true|type|unsafe|use|where|while|async|await|dyn|try)\b/g,
                priority: 7
            },
            {
                type: 'number',
                regex: /\b0x[0-9a-fA-F]+(?:_[0-9a-fA-F]+)*\b|\b\d+(?:_\d+)*(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g,
                priority: 6
            }
        ]
    },
    DIFF_LANGUAGE_DEFINITION
];

export { PRIMARY_LANGUAGE_DEFINITIONS };
