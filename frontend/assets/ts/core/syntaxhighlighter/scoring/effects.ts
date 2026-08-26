/* SoAI - Shared frontend syntax highlighter scoring effects [frontend/assets/ts/core/syntaxhighlighter/scoring/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { countMatches } from '@core/syntaxhighlighter/scoring/mappers.ts';

const scoreCsharp = (text: string): number => {
    let score = 0;
    score += countMatches(/\busing\s+System/g, text, 6) * 6;
    score += countMatches(/\bnamespace\s+[A-Za-z_][\w.]*/g, text, 6) * 5;
    score += countMatches(/\bpublic\s+(?:class|interface|struct)\s+[A-Za-z_][\w]*/g, text, 6) * 5;
    score += countMatches(/\bConsole\.[A-Za-z]+/g, text, 10) * 2;
    score += countMatches(/\b(?:async|await|Task|var|List<|IEnumerable<|Nullable<)\b/g, text, 10) * 2;
    score += countMatches(/\[[A-Za-z_][\w]*(?:\([^)]*\))?]/g, text, 6) * 2;
    return score;
};

const scoreXml = (text: string, trimmed: string): number => {
    if (!trimmed.startsWith('<')) {
        return 0;
    }
    let score = 0;
    score += countMatches(/<\?xml\b[^>]*?>/g, text, 2) * 30;
    score += countMatches(/<\/?[A-Za-z_:][\w:.-]*(\s+[A-Za-z_:][\w:.-]*(\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*\s*\/?>/g, text, 40) * 2;
    score += countMatches(/<!--[\s\S]*?-->/g, text, 6) * 4;
    return score;
};

const scoreRuby = (text: string): number => {
    let score = 0;
    score += countMatches(/\bdef\s+[A-Za-z_][\w]*[?!]?\s*(\(|\n|$)/g, text, 6) * 8;
    score += countMatches(/\bend\b/g, text, 12) * 4;
    score += countMatches(/\bdo\b/g, text, 10) * 2;
    score += countMatches(/@[A-Za-z_][\w]*/g, text, 8) * 3;
    score += countMatches(/:[A-Za-z_][\w]*/g, text, 10) * 2;
    score += countMatches(/\|\|=/g, text, 6) * 4;
    score += countMatches(/\b(?:require|module|class|attr_reader|attr_writer|attr_accessor)\b/g, text, 8) * 3;
    score += countMatches(/\b(?:puts|gets)\b/g, text, 6) * 2;
    return score;
};

const scoreJava = (text: string): number => {
    let score = 0;
    score += countMatches(/\bpublic\s+class\s+[A-Za-z_][\w]*/g, text, 4) * 10;
    score += countMatches(/\bpackage\s+[A-Za-z_][\w.]*;/g, text, 2) * 8;
    score += countMatches(/\bpublic\s+static\s+void\s+main\s*\(/g, text, 2) * 12;
    score += countMatches(/\bimport\s+[A-Za-z_][\w.]*;/g, text, 6) * 4;
    score += countMatches(/\b(?:private|protected|public)\s+[A-Za-z_][\w]*\s+[A-Za-z_][\w]*\s*\(/g, text, 6) * 3;
    score += countMatches(/\b(?:extends|implements|abstract|final|static)\b/g, text, 8) * 2;
    score += countMatches(/\bSystem\.out\.println\s*\(/g, text, 4) * 4;
    return score;
};

const scoreC = (text: string): number => {
    let score = 0;
    score += countMatches(/#include\s*[<"][^>"]+[>"]/g, text, 6) * 8;
    score += countMatches(/\bint\s+main\s*\(/g, text, 2) * 10;
    score += countMatches(/\b(?:printf|scanf|fprintf|malloc|free|sizeof)\s*\(/g, text, 10) * 4;
    score += countMatches(/\b(?:int|char|float|double|void|long|short|unsigned|signed)\s+[A-Za-z_][\w]*/g, text, 10) * 2;
    score += countMatches(/->/g, text, 8) * 3;
    score += countMatches(/\*[A-Za-z_][\w]*/g, text, 8) * 1;
    score += countMatches(/\b(?:struct|typedef|union|enum)\s+[A-Za-z_][\w]*/g, text, 6) * 3;
    return score;
};

const scoreSql = (text: string): number => {
    let score = 0;
    score += countMatches(/\bSELECT\s+[^\n]+\s+FROM\b/gi, text, 8) * 10;
    score += countMatches(/\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE)\b/gi, text, 6) * 8;
    score += countMatches(/\b(?:WHERE|JOIN|INNER\s+JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|ON|GROUP\s+BY|ORDER\s+BY|HAVING)\b/gi, text, 10) * 4;
    score += countMatches(/\b(?:SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TABLE|INDEX|VIEW)\b/gi, text, 12) * 2;
    score += countMatches(/\b(?:VARCHAR|INT|INTEGER|DATETIME|TEXT|BLOB|PRIMARY\s+KEY|FOREIGN\s+KEY)\b/gi, text, 8) * 3;
    return score;
};

const scoreSwift = (text: string): number => {
    let score = 0;
    score += countMatches(/\bfunc\s+[A-Za-z_][\w]*\s*\(/g, text, 6) * 8;
    score += countMatches(/\b(?:var|let)\s+[A-Za-z_][\w]*\s*:\s*[A-Za-z_][\w]*/g, text, 8) * 4;
    score += countMatches(/\b(?:var|let)\s+[A-Za-z_][\w]*\s*=/g, text, 8) * 2;
    score += countMatches(/@[A-Za-z_][\w]*/g, text, 6) * 4;
    score += countMatches(/\?\./g, text, 8) * 3;
    score += countMatches(/\b(?:guard|defer)\b/g, text, 6) * 5;
    score += countMatches(/\b(?:protocol|extension|struct|enum)\s+[A-Za-z_][\w]*/g, text, 6) * 3;
    return score;
};

const scoreKotlin = (text: string): number => {
    let score = 0;
    score += countMatches(/\bfun\s+[A-Za-z_][\w]*\s*\(/g, text, 6) * 8;
    score += countMatches(/\b(?:val|var)\s+[A-Za-z_][\w]*\s*:\s*[A-Za-z_][\w]*/g, text, 6) * 4;
    score += countMatches(/\bdata\s+class\s+[A-Za-z_][\w]*/g, text, 4) * 8;
    score += countMatches(/\?:/g, text, 6) * 5;
    score += countMatches(/\?\./g, text, 8) * 3;
    score += countMatches(/\b(?:companion\s+object|sealed\s+class|inline|suspend)\b/g, text, 6) * 4;
    score += countMatches(/\$\{[^}]+\}/g, text, 8) * 2;
    return score;
};

const scoreDockerfile = (text: string, _trimmed: string): number => {
    let score = 0;
    score += countMatches(/^FROM\s+[^\n]+/gim, text, 3) * 15;
    score += countMatches(/^(?:RUN|COPY|ADD|WORKDIR|ENV|EXPOSE|CMD|ENTRYPOINT|VOLUME|USER|LABEL|ARG|HEALTHCHECK|SHELL|STOPSIGNAL|ONBUILD)\s+/gim, text, 20) * 4;
    return score;
};

const scoreMarkdown = (text: string): number => {
    let score = 0;
    score += countMatches(/^#{1,6}\s+.+$/gm, text, 10) * 3;
    score += countMatches(/\[([^\]]+)\]\(([^)]+)\)/g, text, 10) * 4;
    score += countMatches(/(?:^|\n)```[a-z]*\n[\s\S]*?\n```/g, text, 6) * 8;
    score += countMatches(/(?:\*\*|__)([^*_]+)(?:\*\*|__)/g, text, 10) * 2;
    score += countMatches(/(?:\*|_)([^*_]+)(?:\*|_)/g, text, 10) * 1;
    score += countMatches(/^(?:[-*+]|\d+\.)\s+/gm, text, 15) * 2;
    score += countMatches(/^>\s+.+$/gm, text, 8) * 2;
    return score;
};

export { scoreC, scoreCsharp, scoreDockerfile, scoreJava, scoreKotlin, scoreMarkdown, scoreRuby, scoreSql, scoreSwift, scoreXml };
