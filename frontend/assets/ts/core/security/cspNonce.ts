/* SoAI - Shared security CSP nonce [frontend/assets/ts/core/security/cspNonce.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const readNonceFromMetaElement = (meta: HTMLMetaElement): string | null => {
    const nonceValue = meta.nonce;
    if (typeof nonceValue === 'string') {
        const trimmed = nonceValue.trim();
        if (trimmed) return trimmed;
    }

    const contentValue = meta.content;
    if (typeof contentValue === 'string') {
        const trimmed = contentValue.trim();
        if (trimmed) return trimmed;
    }

    return null;
};

const findMetaNonce = (doc: Document, attributeName: 'property' | 'name', attributeValue: string): string | null => {
    const metas = Array.from(doc.getElementsByTagName('meta'));
    for (const meta of metas) {
        const raw = meta.getAttribute(attributeName);
        if (!raw) {
            continue;
        }
        const normalized = raw.trim().toLowerCase();
        if (normalized !== attributeValue) {
            continue;
        }
        const nonce = readNonceFromMetaElement(meta);
        if (nonce) {
            return nonce;
        }
    }
    return null;
};

const readNonceFromMeta = (doc: Document): string | null => {
    return findMetaNonce(doc, 'property', 'csp-nonce') ?? findMetaNonce(doc, 'name', 'csp-nonce');
};

const readNonceFromExistingElements = (doc: Document): string | null => {
    const scripts = Array.from(doc.getElementsByTagName('script'));
    for (const script of scripts) {
        const nonce = script.nonce;
        if (typeof nonce === 'string') {
            const trimmed = nonce.trim();
            if (trimmed) return trimmed;
        }
    }

    const styles = Array.from(doc.getElementsByTagName('style'));
    for (const style of styles) {
        const nonce = style.nonce;
        if (typeof nonce === 'string') {
            const trimmed = nonce.trim();
            if (trimmed) return trimmed;
        }
    }

    return null;
};

const readNonceFromGlobal = (): string | null => {
    const resolver = globalThis.getSoaiCspNonce;
    if (typeof resolver === 'function') {
        return resolver();
    }

    const globalValue = globalThis.soaiCspNonce;
    if (typeof globalValue === 'string') {
        const trimmed = globalValue.trim();
        if (trimmed) return trimmed;
    }

    return null;
};

const getCspNonce = (options: { document?: Document } = {}): string | null => {
    const globalValue = readNonceFromGlobal();
    if (globalValue) return globalValue;

    const doc = options.document ?? globalThis.document ?? null;
    if (!doc) return null;

    const metaValue = readNonceFromMeta(doc);
    if (metaValue) return metaValue;

    return readNonceFromExistingElements(doc);
};

export { getCspNonce };
