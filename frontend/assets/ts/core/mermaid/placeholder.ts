/* SoAI - Mermaid placeholder markup generator used by rich-text rendering [frontend/assets/ts/core/mermaid/placeholder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { escapeHtml } from '@core/security/textSanitizer.ts';

const MASK_64 = (1n << 64n) - 1n;

const hashStringToUint64 = (text: string): bigint => {
    let hash = 0xcbf29ce484222325n;
    const prime = 0x100000001b3n;
    for (let index = 0; index < text.length; index += 1) {
        hash ^= BigInt(text.charCodeAt(index));
        hash = (hash * prime) & MASK_64;
    }
    return hash & MASK_64;
};

const createMermaidKey = (diagramDefinition: string): string => {
    const normalized = diagramDefinition.trim();
    const hash = hashStringToUint64(normalized);
    return `mmd-${hash.toString(36)}`;
};

const createMermaidPlaceholder = (diagramDefinition: string): string => {
    const escapedDefinition = escapeHtml(diagramDefinition).replace(/\n/g, '&#10;');
    const mermaidKey = createMermaidKey(diagramDefinition);
    return `<div class="mermaid-container mermaid-loading" data-mermaid-key="${mermaidKey}" data-mermaid-definition="${escapedDefinition}"><div class="mermaid-spinner"></div></div>`;
};

export { createMermaidPlaceholder };
