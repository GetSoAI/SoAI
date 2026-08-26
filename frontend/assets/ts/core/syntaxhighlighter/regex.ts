/* SoAI - Shared frontend syntax highlighter regex [frontend/assets/ts/core/syntaxhighlighter/regex.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const safeCloneRegex = (regex: RegExp): RegExp => {
    const flags = regex.flags.includes('g') ? regex.flags : `${regex.flags}g`;
    return new RegExp(regex.source, flags);
};

export { safeCloneRegex };
