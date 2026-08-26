/* SoAI - CSP nonce injection for vendored Mermaid assets [frontend/scripts/cspNonceVendorMermaid.mts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

type PatchResult = {
    filePath: string;
    updated: boolean;
    replacements: number;
};

const MERMAID_NONCE_MARKER = '__soai_mermaid_style_nonce__';
const MERMAID_NONCE_MARKER_PATTERN = /\n[ \t\r\n]*\/\* __soai_mermaid_style_nonce__ \*\/[ \t\r\n]*$/;
const NONCE_INJECTION_PREFIX = '(()=>{const styleElement=';

const resolveNonceReadExpression = (): string => {
    return ['typeof globalThis.getSoaiCspNonce==="function"?globalThis.getSoaiCspNonce():', 'typeof globalThis.soaiCspNonce==="string"?(()=>{const value=globalThis.soaiCspNonce;return typeof value==="string"?value.trim():""})():', '(()=>{const doc=globalThis.document;if(!doc)return"";', 'const metas=doc.getElementsByTagName("meta");', 'for(let i=0;i<metas.length;i+=1){const meta=metas[i];if(!(meta instanceof HTMLMetaElement))continue;', 'const property=meta.getAttribute("property");const name=meta.getAttribute("name");', 'const key=(property??name??"").trim().toLowerCase();if(key!=="csp-nonce")continue;', 'const nonce=(meta.nonce||meta.content||"").trim();if(nonce)return nonce;}', 'return"";})()'].join('');
};

const resolveNonceAssignmentExpression = (targetExpression: string): string => {
    const nonceReadExpression = resolveNonceReadExpression();
    return `(()=>{const styleElement=${targetExpression};if(styleElement instanceof HTMLStyleElement&&!styleElement.nonce){const nonceValue=${nonceReadExpression};if(nonceValue)styleElement.nonce=nonceValue}})()`;
};

const patchDeclaredStyleCreationSites = (runtimeText: string): { runtimeText: string; replacements: number } => {
    const pattern = /(const|let|var)\s+([A-Za-z_$][0-9A-Za-z_$]*)\s*=\s*([A-Za-z_$][0-9A-Za-z_$]*(?:\.[A-Za-z_$][0-9A-Za-z_$]*)*)\.createElement\(("|')style\4\);(?!\(\(\)=>\{const styleElement=)/g;
    let replacements = 0;
    const updatedRuntimeText = runtimeText.replace(pattern, (_match, declarationKeyword: string, variableName: string, creatorExpression: string, quote: string) => {
        replacements += 1;
        return `${declarationKeyword} ${variableName}=${creatorExpression}.createElement(${quote}style${quote});${resolveNonceAssignmentExpression(variableName)};`;
    });
    return { runtimeText: updatedRuntimeText, replacements };
};

const patchAssignedStyleCreationSites = (runtimeText: string): { runtimeText: string; replacements: number } => {
    const pattern = /([A-Za-z_$][0-9A-Za-z_$]*(?:\.[A-Za-z_$][0-9A-Za-z_$]*)*)\s*=\s*([A-Za-z_$][0-9A-Za-z_$]*(?:\.[A-Za-z_$][0-9A-Za-z_$]*)*)\.createElement\(("|')style\3\);(?!\(\(\)=>\{const styleElement=)/g;
    let replacements = 0;
    const updatedRuntimeText = runtimeText.replace(pattern, (match, targetExpression: string) => {
        replacements += 1;
        return `${match}${resolveNonceAssignmentExpression(targetExpression)};`;
    });
    return { runtimeText: updatedRuntimeText, replacements };
};

const patchMermaidRuntimeText = (runtimeText: string): { runtimeText: string; replacements: number } => {
    const normalizedRuntimeText = runtimeText.replace(MERMAID_NONCE_MARKER_PATTERN, '').trimEnd();
    const assignedStyleResult = patchAssignedStyleCreationSites(normalizedRuntimeText);
    const declaredStyleResult = patchDeclaredStyleCreationSites(assignedStyleResult.runtimeText);
    const replacements = assignedStyleResult.replacements + declaredStyleResult.replacements;

    if (replacements === 0) {
        if (normalizedRuntimeText.includes(NONCE_INJECTION_PREFIX)) {
            return {
                runtimeText: `${normalizedRuntimeText}\n/* ${MERMAID_NONCE_MARKER} */\n`,
                replacements: 0
            };
        }
        return { runtimeText, replacements: 0 };
    }

    return {
        runtimeText: `${declaredStyleResult.runtimeText}\n/* ${MERMAID_NONCE_MARKER} */\n`,
        replacements
    };
};

const patchMermaidRuntimeFile = async (filePath: string): Promise<PatchResult> => {
    const original = await fs.readFile(filePath, 'utf8');
    const { runtimeText, replacements } = patchMermaidRuntimeText(original);
    const normalizedOriginal = original.replace(MERMAID_NONCE_MARKER_PATTERN, '').trimEnd();
    const hasStyleCreationSite = normalizedOriginal.includes('.createElement("style")') || normalizedOriginal.includes(".createElement('style')");
    const hasCurrentNonceInjection = runtimeText.includes(NONCE_INJECTION_PREFIX) && runtimeText.includes('globalThis.getSoaiCspNonce') && runtimeText.includes('globalThis.soaiCspNonce');
    if (hasStyleCreationSite && replacements === 0 && !hasCurrentNonceInjection) {
        throw new Error(`CSP nonce injection failed: unsupported style creation pattern in ${filePath}`);
    }
    if (!hasStyleCreationSite) {
        throw new Error(`CSP nonce injection failed: no style creation sites found in ${filePath}`);
    }
    await fs.writeFile(filePath, runtimeText, 'utf8');
    return { filePath, updated: runtimeText !== original, replacements };
};

const patchMermaid = async (): Promise<void> => {
    const root = path.resolve(process.cwd());
    const filePath = path.join(root, 'node_modules', 'mermaid', 'dist', 'mermaid.core.mjs');
    const result = await patchMermaidRuntimeFile(filePath);
    if (result.updated) {
        process.stdout.write(`Patched mermaid for CSP nonces: ${result.filePath} (${result.replacements} replacements)\n`);
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
    await patchMermaid();
}

export { patchMermaid, patchMermaidRuntimeText };
