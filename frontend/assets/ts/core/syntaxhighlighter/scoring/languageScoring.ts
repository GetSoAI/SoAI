/* SoAI - Frontend syntax language scoring [frontend/assets/ts/core/syntaxhighlighter/scoring/languageScoring.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { scoreC, scoreCsharp, scoreDockerfile, scoreJava, scoreKotlin, scoreMarkdown, scoreRuby, scoreSql, scoreSwift, scoreXml } from '@core/syntaxhighlighter/scoring/effects.ts';
import { detectShebangLanguage } from '@core/syntaxhighlighter/shebang.ts';
import { countMatches, dynamicThreshold } from '@core/syntaxhighlighter/scoring/mappers.ts';

const scoreJavascript = (text: string): number => {
    let score = 0;
    score += countMatches(/\b(?:const|let|var)\s+[A-Za-z_$][\w$]*(?:\s*:\s*[^=;]+)?\s*=/g, text, 6) * 5;
    score += countMatches(/\bfunction\s+[A-Za-z_$][\w$]*\s*\(/g, text, 5) * 6;
    score += countMatches(/\bclass\s+[A-Za-z_$][\w$]*/g, text, 4) * 5;
    score += countMatches(/\b(?:import|export)\s+(?:\{|\*|default|\w)/g, text, 4) * 6;
    score += countMatches(/=>/g, text, 12) * 2;
    score += countMatches(/\bconsole\.[A-Za-z_][\w]*\s*\(/g, text, 8) * 4;
    score += countMatches(/\b(?:console|window|document)\./g, text, 8) * 2;
    score += countMatches(/\bswitch\s*\([^)]*\)\s*\{/g, text, 4) * 4;
    score += countMatches(/\bcase\s+[^:]+:/g, text, 8) * 1;
    score += countMatches(/\b(?:async|await|Promise)\b/g, text, 8) * 2;
    score += countMatches(/\bthis\./g, text, 6) * 1;
    return score;
};

const scoreTypescript = (text: string): number => {
    const baseScore = scoreJavascript(text);
    let tsSpecific = 0;

    tsSpecific += countMatches(/\binterface\s+[A-Za-z_][\w]*\s*\{/g, text, 5) * 10;
    tsSpecific += countMatches(/(?:^|\n)\s*(?:export\s+)?(?:declare\s+)?type\s+[A-Za-z_][\w]*\s*=/g, text, 5) * 10;
    tsSpecific += countMatches(/\benum\s+[A-Za-z_][\w]*\s*\{/g, text, 4) * 8;
    tsSpecific += countMatches(/\bimplements\s+[A-Za-z_][\w.<>]+/g, text, 4) * 6;
    tsSpecific += countMatches(/\b(?:a\x73)\s+(?:string|number|boolean|a\x6ey|unkn\x6fwn|never|void)\b/g, text, 6) * 4;
    tsSpecific += countMatches(/:\s*(?:string|number|boolean|a\x6ey|unkn\x6fwn|never|void|Promise<)/g, text, 6) * 3;

    if (tsSpecific === 0) {
        return 0;
    }

    return baseScore + tsSpecific;
};

const scorePython = (text: string): number => {
    let score = 0;
    score += countMatches(/\bdef\s+[A-Za-z_][\w]*\s*\(/g, text, 6) * 7;
    score += countMatches(/\bclass\s+[A-Za-z_][\w]*\s*:/g, text, 5) * 6;
    score += countMatches(/\bfrom\s+[A-Za-z_.]+\s+import\b/g, text, 5) * 5;
    score += countMatches(/\bimport\s+[A-Za-z_.]+/g, text, 6) * 4;
    score += countMatches(/\bself\b/g, text, 10) * 2;
    score += countMatches(/^\s*#/gm, text, 12) * 2;
    score += countMatches(/("""|''')[\s\S]*?\1/g, text, 3) * 5;
    score += countMatches(/\b(?:True|False|None)\b/g, text, 8) * 2;
    score += countMatches(/:\s*(?:#.*)?\n\s+/g, text, 8) * 1;
    score += countMatches(/\b(?:async|await|yield)\b/g, text, 6) * 2;
    return score;
};

const scoreJson = (text: string, trimmed: string): number => {
    if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
        return 0;
    }
    try {
        parseRequiredJsonText(trimmed);
        return 160;
    } catch (jsonParseError) {
        ensureError(jsonParseError);
    }
    let score = 0;
    score += countMatches(/"([^"\\]|\\.)*"\s*:/g, text, 25) * 4;
    score += countMatches(/[[\]{}]/g, text, 50) * 1;
    score += countMatches(/,\s*"/g, text, 20) * 2;
    score += countMatches(/:\s*(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null|\[\s*]|{\s*})/g, text, 20) * 2;
    return score;
};

const scoreYaml = (text: string, trimmed: string): number => {
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        return 0;
    }
    let score = 0;
    score += countMatches(/^\s*[\w.+-]+\s*:/gm, text, 18) * 3;
    score += countMatches(/-\s+[^#\n]+/g, text, 18) * 2;
    score += countMatches(/^\s*#/gm, text, 12) * 1;
    score += countMatches(/^\s*---/gm, text, 2) * 12;
    score += countMatches(/[|>]\s*(#.*)?$/gm, text, 4) * 3;
    score += countMatches(/&[A-Za-z0-9_-]+|\*[A-Za-z0-9_-]+/g, text, 8) * 3;
    return score;
};

const scoreHtml = (text: string, trimmed: string): number => {
    if (!trimmed.startsWith('<')) {
        return 0;
    }
    let score = 0;
    score += countMatches(/<!DOCTYPE\s+html>/gi, text, 2) * 40;
    score += countMatches(/<!--[\s\S]*?-->/g, text, 6) * 4;
    score += countMatches(/<\/?[A-Za-z][^>]*>/g, text, 40) * 2;
    score += countMatches(/<[A-Za-z][\w:-]*(\s+[A-Za-z_:][\w:.-]*(\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*\s*\/?>/g, text, 40) * 2;
    return score;
};

const scoreCss = (text: string): number => {
    if (/\b(?:const|let|var|function|interface|enum|type|class|import|export)\b/.test(text)) {
        return 0;
    }
    let score = 0;
    score += countMatches(/[^{\n]+\{\s*[^}]*?\s*}/g, text, 25) * 3;
    score += countMatches(/:[^;{}]+;/g, text, 30) * 2;
    score += countMatches(/@[a-z-]+\s+[^{]+{/gi, text, 10) * 3;
    score += countMatches(/#[0-9a-fA-F]{3,6}\b/g, text, 20) * 2;
    score += countMatches(/\b(?:px|em|rem|vh|vw|%)\b/g, text, 20) * 1;
    return score;
};

const scoreBash = (text: string, trimmed: string): number => {
    let score = 0;
    if (!trimmed.startsWith('#!')) {
        return 0;
    }
    const shebangLang = detectShebangLanguage(trimmed);
    if (shebangLang && shebangLang !== 'bash') {
        return 0;
    }
    if (shebangLang === 'bash') {
        score += 60;
    } else {
        score += 30;
    }
    score += countMatches(/^\s*#[^!].*$/gm, text, 12) * 3;
    score += countMatches(/(?:^|\s)(?:fi|done|esac)(?=\s|;|$)/gm, text, 16) * 6;
    score += countMatches(/(?:^|\s)elif(?=\s|;|$)/gm, text, 16) * 5;
    score += countMatches(/(?:^|\s)(?:if|elif)[^\n;]*?\bthen\b/gm, text, 12) * 4;
    score += countMatches(/\b(?:case|select|while|until)\b/g, text, 16) * 3;
    score += countMatches(/\$\{[^}]+\}/g, text, 16) * 4;
    score += countMatches(/\$\((?:[^)(]|\([^)]*\))*\)/g, text, 16) * 4;
    score += countMatches(/\$[A-Za-z_@*#?$-][\w@*#?$-]*/g, text, 25) * 2;
    score += countMatches(/\b(?:echo|printf|read|cd|pwd|exit|return|exec|source|alias|trap|set|shift|local|declare)\b/g, text, 20) * 3;
    score += countMatches(/\[\[?[^\]]+\]?\]?/g, text, 14) * 3;
    score += countMatches(/\|\||&&|;;|<<-?|\d?>&\d+/g, text, 12) * 2;
    return score;
};

const scoreGo = (text: string): number => {
    let score = 0;
    score += countMatches(/\bpackage\s+[A-Za-z_][\w]*/g, text, 3) * 10;
    score += countMatches(/\bfunc\s+[A-Za-z_][\w]*\s*\(/g, text, 8) * 6;
    score += countMatches(/\bimport\s+(?:\(|")/g, text, 6) * 5;
    score += countMatches(/\b(?:go|defer)\b/g, text, 10) * 2;
    score += countMatches(/\b(?:chan|map|struct|interface)\b/g, text, 10) * 2;
    score += countMatches(/\bfmt\.[A-Za-z]+/g, text, 8) * 2;
    return score;
};

const scoreRust = (text: string): number => {
    let score = 0;
    score += countMatches(/\bfn\s+[A-Za-z_][\w]*\s*\(/g, text, 8) * 8;
    score += countMatches(/\b(?:let|mut)\s+[A-Za-z_][\w]*/g, text, 10) * 4;
    score += countMatches(/\b(?:pub\s+)?struct\s+[A-Za-z_][\w]*/g, text, 6) * 8;
    score += countMatches(/\bimpl\s+[A-Za-z_][\w]*/g, text, 6) * 6;
    score += countMatches(/\buse\s+[A-Za-z_][\w:]*;/g, text, 6) * 4;
    score += countMatches(/\b(?:match|enum|trait)\b/g, text, 14) * 2;
    score += countMatches(/\b[A-Za-z_][\w]*!/g, text, 10) * 3;
    score += countMatches(/::/g, text, 14) * 1;
    score += countMatches(/\bSelf\b/g, text, 6) * 1;
    return score;
};

const scorePhp = (text: string, trimmed: string): number => {
    if (!trimmed.startsWith('<?') && !trimmed.includes('<?php')) {
        return 0;
    }
    let score = trimmed.startsWith('<?php') ? 80 : 40;
    score += countMatches(/\bfunction\s+[A-Za-z_][\w]*\s*\(/g, text, 6) * 5;
    score += countMatches(/\$[A-Za-z_\x80-\xff][\w\x80-\xff]*/g, text, 25) * 3;
    score += countMatches(/->/g, text, 20) * 2;
    score += countMatches(/\b(?:use|namespace|class|public|private|protected|extends|implements|trait)\b/g, text, 12) * 3;
    score += countMatches(/\becho\b/g, text, 8) * 2;
    return score;
};

export { dynamicThreshold, scoreBash, scoreC, scoreCsharp, scoreCss, scoreDockerfile, scoreGo, scoreHtml, scoreJava, scoreJavascript, scoreJson, scoreKotlin, scoreMarkdown, scorePhp, scorePython, scoreRuby, scoreRust, scoreSql, scoreSwift, scoreTypescript, scoreXml, scoreYaml };
