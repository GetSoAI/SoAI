/* SoAI - CSP nonce injection for vendored Xterm assets [frontend/scripts/cspNonceVendorXterm.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

type PatchResult = {
    filePath: string;
    updated: boolean;
    replacements: number;
};

const XTERM_NONCE_MARKER = '__soai_xterm_style_nonce__';
const XTERM_NONCE_MARKER_PATTERN = /\n[ \t\r\n]*\/\* __soai_xterm_style_nonce__ \*\/[ \t\r\n]*$/;
const XTERM_NONCE_INJECTION_PATTERN = /\(\(\)=>\{const styleElement=[A-Za-z_$][0-9A-Za-z_$]*(?:\.[A-Za-z_$][0-9A-Za-z_$]*)*;if\(styleElement instanceof HTMLStyleElement&&!styleElement\.nonce\)\{const nonceValue=[^;\n]+;const trimmedNonce=[^;\n]+;if\(trimmedNonce\)styleElement\.nonce=trimmedNonce\}\}\)\(\)[,;]?/g;

const resolveNonceAssignmentExpression = (targetExpression: string): string => {
    return `(()=>{const styleElement=${targetExpression};if(styleElement instanceof HTMLStyleElement&&!styleElement.nonce){const nonceValue=typeof globalThis.getSoaiCspNonce==="function"?globalThis.getSoaiCspNonce():typeof globalThis.soaiCspNonce==="string"?globalThis.soaiCspNonce:null;const trimmedNonce=typeof nonceValue==="string"?nonceValue.trim():"";if(trimmedNonce)styleElement.nonce=trimmedNonce}})()`;
};

const patchAssignedStyleCreationSites = (runtimeText: string): { runtimeText: string; replacements: number } => {
    const pattern = /([A-Za-z_$][0-9A-Za-z_$]*(?:\.[A-Za-z_$][0-9A-Za-z_$]*)*)=([A-Za-z_$][0-9A-Za-z_$]*(?:\.[A-Za-z_$][0-9A-Za-z_$]*)*)\.createElement\(("|')style\3\),(?!\(\(\)=>\{const styleElement=)/g;
    let replacements = 0;
    const updatedRuntimeText = runtimeText.replace(pattern, (match, targetExpression: string) => {
        replacements += 1;
        return `${match}${resolveNonceAssignmentExpression(targetExpression)},`;
    });
    return { runtimeText: updatedRuntimeText, replacements };
};

const patchDeclaredStyleCreationSites = (runtimeText: string): { runtimeText: string; replacements: number } => {
    const pattern = /(const|let|var)\s+([A-Za-z_$][0-9A-Za-z_$]*)=([A-Za-z_$][0-9A-Za-z_$]*(?:\.[A-Za-z_$][0-9A-Za-z_$]*)*)\.createElement\(("|')style\4\);(?!\(\(\)=>\{const styleElement=)/g;
    let replacements = 0;
    const updatedRuntimeText = runtimeText.replace(pattern, (_match, declarationKeyword: string, variableName: string, creatorExpression: string, quote: string) => {
        replacements += 1;
        return `${declarationKeyword} ${variableName}=${creatorExpression}.createElement(${quote}style${quote});${resolveNonceAssignmentExpression(variableName)};`;
    });
    return { runtimeText: updatedRuntimeText, replacements };
};

const patchXtermRuntimeText = (runtimeText: string): { runtimeText: string; replacements: number } => {
    const normalizedRuntimeText = runtimeText.replace(XTERM_NONCE_MARKER_PATTERN, '').replace(XTERM_NONCE_INJECTION_PATTERN, '').trimEnd();
    const assignedStyleResult = patchAssignedStyleCreationSites(normalizedRuntimeText);
    const declaredStyleResult = patchDeclaredStyleCreationSites(assignedStyleResult.runtimeText);
    const replacements = assignedStyleResult.replacements + declaredStyleResult.replacements;

    if (replacements === 0) {
        return { runtimeText, replacements: 0 };
    }

    return {
        runtimeText: `${declaredStyleResult.runtimeText}\n/* ${XTERM_NONCE_MARKER} */\n`,
        replacements
    };
};

const patchXtermRuntimeFile = async (filePath: string): Promise<PatchResult> => {
    const original = await fs.readFile(filePath, 'utf8');
    const { runtimeText, replacements } = patchXtermRuntimeText(original);
    if (replacements === 0 && runtimeText === original) {
        throw new Error(`CSP nonce injection failed: pattern not found in ${filePath}`);
    }
    await fs.writeFile(filePath, runtimeText, 'utf8');
    return { filePath, updated: runtimeText !== original, replacements };
};

const patchXterm = async (): Promise<void> => {
    const root = path.resolve(process.cwd());
    const runtimeFiles = [path.join(root, 'node_modules', '@xterm', 'xterm', 'lib', 'xterm.mjs'), path.join(root, 'node_modules', '@xterm', 'xterm', 'lib', 'xterm.js')];

    const results: PatchResult[] = [];
    for (const filePath of runtimeFiles) {
        try {
            await fs.access(filePath);
        } catch {
            continue;
        }
        results.push(await patchXtermRuntimeFile(filePath));
    }

    if (results.length === 0) {
        throw new Error('CSP nonce injection failed: no xterm runtime files found');
    }

    const updatedAny = results.some((result) => result.updated);
    if (updatedAny) {
        const summary = results
            .filter((result) => result.updated)
            .map((result) => `${result.filePath} (${result.replacements} replacements)`)
            .join(', ');
        process.stdout.write(`Patched xterm for CSP nonces: ${summary}\n`);
    }
};

const shouldRunAsScript = (): boolean => {
    const scriptPath = process.argv[1];
    if (!scriptPath) {
        return false;
    }
    return import.meta.url === pathToFileURL(scriptPath).href;
};

if (shouldRunAsScript()) {
    await patchXterm();
}

export { patchXterm, patchXtermRuntimeText };
