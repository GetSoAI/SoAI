/* SoAI - Shared frontend syntax highlighter mapping [frontend/assets/ts/core/syntaxhighlighter/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scoreC, scoreCsharp, scoreDockerfile, scoreJava, scoreKotlin, scoreMarkdown, scorePhp, scoreRuby, scoreSql, scoreSwift, scoreXml } from '@core/syntaxhighlighter/scoring/public.ts';
import type { LanguageDefinition } from '@core/syntaxhighlighter/types.ts';

const SECONDARY_LANGUAGE_DEFINITIONS: LanguageDefinition[] = [
    {
        id: 'php',
        label: '',
        aliases: [],
        score: (text: string, trimmed?: string): number => scorePhp(text, trimmed ?? text.trim()),
        grammar: [
            { type: 'comment', regex: /\/\/[^\n]*|\/\*[\s\S]*?\*\/|#[^\n]*/g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`|'(?:\\.|[^'\\])*'/g, priority: 8 },
            {
                type: 'keyword',
                regex: /\b(?:abstract|and|array|a\x73|break|callable|case|catch|class|clone|const|continue|declare|default|do|else|elseif|enddeclare|endfor|endforeach|endif|endswitch|endwhile|extends|final|finally|fn|for|foreach|function|global|goto|if|implements|include|include_once|instanceof|insteadof|interface|namespace|new|or|private|protected|public|require|require_once|return|static|switch|throw|trait|try|use|var|while|xor|yield)\b/gi,
                priority: 7
            },
            { type: 'variable', regex: /\$[A-Za-z_\x80-\xff][A-Za-z0-9_\x80-\xff]*/g, priority: 7 },
            { type: 'builtin', regex: /\b(?:echo|print|array|isset|empty|count)\b/g, priority: 6 },
            { type: 'number', regex: /\b\d+(?:\.\d+)?\b/g, priority: 5 }
        ]
    },
    {
        id: 'csharp',
        label: '',
        aliases: ['cs'],
        score: (text: string): number => scoreCsharp(text),
        grammar: [
            { type: 'comment', regex: /\/\/[^\n]*|\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /@"[^"]*"|"(?:\\.|[^"\\])*"/g, priority: 8 },
            {
                type: 'keyword',
                regex: /\b(?:abstract|a\x73|base|bool|break|byte|case|catch|char|checked|class|const|continue|decimal|default|delegate|do|double|else|enum|event|explicit|extern|false|finally|fixed|float|for|foreach|goto|if|implicit|in|int|interface|internal|is|lock|long|namespace|new|null|object|operator|out|override|params|private|protected|public|readonly|ref|return|sbyte|sealed|short|sizeof|stackalloc|static|string|struct|switch|this|throw|true|try|typeof|uint|ulong|unchecked|unsafe|ushort|using|virtual|void|volatile|while)\b/g,
                priority: 7
            },
            { type: 'attribute', regex: /\[[A-Za-z_][\w]*(?:\([^)]*\))?]/g, priority: 6 },
            { type: 'number', regex: /\b\d+(?:\.\d+)?\b/g, priority: 5 }
        ]
    },
    {
        id: 'xml',
        label: '',
        aliases: [],
        score: (text: string, trimmed?: string): number => scoreXml(text, trimmed ?? text.trim()),
        grammar: [
            { type: 'comment', regex: /<!--[\s\S]*?-->/g, priority: 9 },
            { type: 'declaration', regex: /<\?xml\b[^>]*?>/g, priority: 8 },
            { type: 'tag', regex: /<\/?[A-Za-z_:][\w:.-]*/g, priority: 8 },
            { type: 'attr-name', regex: /(?:\s+)([A-Za-z_:][A-Za-z0-9:._-]*)(?=\s*=)/g, priority: 7, group: 1 },
            { type: 'attr-value', regex: /=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/g, priority: 7 }
        ]
    },
    {
        id: 'ruby',
        label: '',
        aliases: ['rb'],
        score: (text: string): number => scoreRuby(text),
        grammar: [
            { type: 'comment', regex: /#[^\n]*/g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, priority: 8 },
            { type: 'symbol', regex: /:[A-Za-z_][\w]*/g, priority: 7 },
            { type: 'instance-var', regex: /@[A-Za-z_][\w]*/g, priority: 7 },
            {
                type: 'keyword',
                regex: /\b(?:def|end|class|module|if|unless|while|until|for|do|begin|rescue|ensure|raise|return|yield|self|super|require|include|extend|attr_reader|attr_writer|attr_accessor|alias|break|next|redo|retry|case|when|then|else|elsif|puts|gets|print)\b/g,
                priority: 7
            }
        ]
    },
    {
        id: 'java',
        label: '',
        aliases: [],
        score: (text: string): number => scoreJava(text),
        grammar: [
            { type: 'comment', regex: /\/\/[^\n]*|\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 8 },
            {
                type: 'keyword',
                regex: /\b(?:abstract|assert|boolean|break|byte|case|catch|char|class|const|continue|default|do|double|else|enum|extends|final|finally|float|for|goto|if|implements|import|instanceof|int|interface|long|native|new|package|private|protected|public|return|short|static|strictfp|super|switch|synchronized|this|throw|throws|transient|try|void|volatile|while)\b/g,
                priority: 7
            },
            { type: 'annotation', regex: /@[A-Za-z_][\w.]*/g, priority: 7 }
        ]
    },
    {
        id: 'c',
        label: '',
        aliases: ['cpp', 'cc', 'cxx', 'h', 'hpp'],
        score: (text: string): number => scoreC(text),
        grammar: [
            { type: 'comment', regex: /\/\/[^\n]*|\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 8 },
            {
                type: 'keyword',
                regex: /\b(?:auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|inline|int|long|register|restrict|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while|bool|class|namespace|template|typename|public|private|protected|virtual)\b/g,
                priority: 7
            },
            {
                type: 'builtin',
                regex: /\b(?:printf|scanf|fprintf|malloc|free|memcpy|strlen|strcpy|strcmp)\b/g,
                priority: 6
            },
            {
                type: 'number',
                regex: /\b0x[0-9a-fA-F]+[UuLl]*\b|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[FfLl]?\b/g,
                priority: 5
            }
        ]
    },
    {
        id: 'sql',
        label: '',
        aliases: ['mysql', 'postgres', 'postgresql', 'sqlite'],
        score: (text: string): number => scoreSql(text),
        grammar: [
            { type: 'comment', regex: /--[^\n]*/g, priority: 9 },
            { type: 'comment', regex: /\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /'(?:''|[^'])*'/g, priority: 8 },
            {
                type: 'keyword',
                regex: /\b(?:SELECT|FROM|WHERE|INSERT|INTO|UPDATE|DELETE|CREATE|ALTER|DROP|TABLE|INDEX|VIEW|DATABASE|JOIN|INNER|LEFT|RIGHT|OUTER|ON|GROUP|BY|ORDER|HAVING|A\x53|DISTINCT|COUNT|SUM|AVG|MAX|MIN|AND|OR|NOT|NULL|IS|IN|BETWEEN)\b/gi,
                priority: 7
            },
            {
                type: 'type',
                regex: /\b(?:VARCHAR|INT|INTEGER|BIGINT|SMALLINT|DECIMAL|NUMERIC|FLOAT|DOUBLE|REAL|DATE|TIME|DATETIME|TIMESTAMP|CHAR|TEXT|BLOB|BOOLEAN)\b/gi,
                priority: 6
            },
            { type: 'number', regex: /\b\d+(?:\.\d+)?\b/g, priority: 5 }
        ]
    },
    {
        id: 'swift',
        label: '',
        aliases: [],
        score: (text: string): number => scoreSwift(text),
        grammar: [
            { type: 'comment', regex: /\/\/[^\n]*|\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 8 },
            { type: 'attribute', regex: /@[A-Za-z_][\w]*/g, priority: 7 },
            {
                type: 'keyword',
                regex: /\b(?:associatedtype|class|deinit|enum|extension|fileprivate|func|import|init|inout|internal|let|open|operator|private|protocol|public|rethrows|static|struct|subscript|typealias|var|break|case|continue|default|defer|do|else|fallthrough|for|guard|if|in|repeat|return|switch|where|while|a\x73|Any|catch|false|is|nil|super|self|Self|throw|throws|true|try)\b/g,
                priority: 7
            },
            {
                type: 'type',
                regex: /\b(?:Int|String|Double|Float|Bool|Array|Dictionary|Set|Optional)\b/g,
                priority: 6
            },
            { type: 'number', regex: /\b0x[0-9a-fA-F]+\b|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b/g, priority: 5 }
        ]
    },
    {
        id: 'kotlin',
        label: '',
        aliases: ['kt', 'kts'],
        score: (text: string): number => scoreKotlin(text),
        grammar: [
            { type: 'comment', regex: /\/\/[^\n]*|\/\*[\s\S]*?\*\//g, priority: 9 },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"/g, priority: 8 },
            { type: 'string-template', regex: /\$\{[^}]+\}|\$[A-Za-z_][\w]*/g, priority: 7 },
            {
                type: 'keyword',
                regex: /\b(?:abstract|actual|annotation|a\x73|break|by|catch|class|companion|const|constructor|continue|crossinline|data|do|dynamic|else|enum|expect|external|false|final|finally|for|fun|get|if|import|in|infix|init|inline|inner|interface|internal|is|lateinit|noinline|null|object|open|operator|out|override|package|private|protected|public|reified|return|sealed|set|super|suspend|tailrec|this|throw|true|try|typealias|typeof|val|var|vararg|when|where|while)\b/g,
                priority: 7
            },
            {
                type: 'type',
                regex: /\b(?:Int|String|Double|Float|Boolean|Long|Short|Byte|Char|Unit|Any|Nothing|List|Map|Set|Array)\b/g,
                priority: 6
            },
            {
                type: 'number',
                regex: /\b0x[0-9a-fA-F]+[Ll]?\b|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[FfLl]?\b/g,
                priority: 5
            }
        ]
    },
    {
        id: 'dockerfile',
        label: '',
        aliases: [],
        score: (text: string, trimmed?: string): number => scoreDockerfile(text, trimmed ?? text.trim()),
        grammar: [
            { type: 'comment', regex: /#[^\n]*/g, priority: 9 },
            {
                type: 'keyword',
                regex: /^(?:FROM|RUN|CMD|LABEL|MAINTAINER|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\b/gim,
                priority: 8
            },
            { type: 'string', regex: /"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'/g, priority: 7 },
            { type: 'variable', regex: /\$[\w{}]+/g, priority: 6 }
        ]
    },
    {
        id: 'markdown',
        label: '',
        aliases: ['md'],
        score: (text: string): number => scoreMarkdown(text),
        grammar: [
            { type: 'heading', regex: /^#{1,6}\s+.+$/gm, priority: 9 },
            { type: 'code-block', regex: /(?:^|\n)```[a-z]*\n[\s\S]*?\n```/g, priority: 10 },
            { type: 'code-inline', regex: /`[^`]+`/g, priority: 8 },
            { type: 'link', regex: /\[([^\]]+)\]\(([^)]+)\)/g, priority: 7 },
            { type: 'bold', regex: /(?:\*\*|__)([^*_]+)(?:\*\*|__)/g, priority: 6 },
            { type: 'italic', regex: /(?:\*|_)([^*_]+)(?:\*|_)/g, priority: 6 },
            { type: 'list', regex: /^(?:[-*+]|\d+\.)\s+/gm, priority: 7 },
            { type: 'blockquote', regex: /^>\s+.+$/gm, priority: 7 }
        ]
    },
    {
        id: 'plaintext',
        label: '',
        aliases: ['text'],
        score: (): number => 1,
        grammar: []
    }
];

export { SECONDARY_LANGUAGE_DEFINITIONS };
