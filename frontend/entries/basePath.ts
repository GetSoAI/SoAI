/* SoAI - Frontend base path entry [frontend/entries/basePath.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

declare global {
    var soaiBasePath: string | undefined;
}

const resolveBasePath = (): string => {
    if (typeof document === 'undefined') {
        throw new Error('Document must be available to resolve SoAI asset base path');
    }
    if (!document.baseURI) {
        throw new Error('Document base URI must be available to resolve SoAI asset base path');
    }
    return new URL('./assets/', document.baseURI).toString();
};

export const ensureAssetBasePath = (): string => {
    if (typeof globalThis.soaiBasePath === 'string') {
        return globalThis.soaiBasePath;
    }
    const resolved = resolveBasePath();
    globalThis.soaiBasePath = resolved;
    return resolved;
};

ensureAssetBasePath();

export {};
