/* SoAI - Frontend application CSP nonce [frontend/assets/ts/app/critical/cspNonce.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDocumentFragment } from '@core/dom/domEnvironment.ts';

interface CspNonceSupportRuntime {
    disconnect(): void;
}

const readNonceFromMeta = (doc: Document): string | null => {
    const propertyMeta = doc.querySelector<HTMLMetaElement>('meta[property="csp-nonce"]');
    const propertyNonce = propertyMeta?.nonce ? propertyMeta.nonce.trim() : '';
    if (propertyNonce) return propertyNonce;
    const propertyContent = propertyMeta?.content ? propertyMeta.content.trim() : '';
    if (propertyContent) return propertyContent;

    const nameMeta = doc.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]');
    const nameNonce = nameMeta?.nonce ? nameMeta.nonce.trim() : '';
    if (nameNonce) return nameNonce;
    const nameContent = nameMeta?.content ? nameMeta.content.trim() : '';
    if (nameContent) return nameContent;

    const nonceScript = doc.querySelector<HTMLScriptElement>('script[nonce]');
    const scriptNonce = nonceScript?.nonce ? nonceScript.nonce.trim() : '';
    if (scriptNonce) return scriptNonce;

    const nonceStyle = doc.querySelector<HTMLStyleElement>('style[nonce]');
    const styleNonce = nonceStyle?.nonce ? nonceStyle.nonce.trim() : '';
    if (styleNonce) return styleNonce;

    return null;
};

const applyNonceIfMissing = (element: Element, getNonce: () => string | null): void => {
    if (element instanceof HTMLStyleElement || element instanceof HTMLScriptElement) {
        if (!element.nonce) {
            const nonce = getNonce();
            if (nonce) {
                element.nonce = nonce;
            }
        }
    }
};

const applyNonceInElementSubtree = (root: Element, getNonce: () => string | null): void => {
    const pendingElements: Element[] = [root];
    while (pendingElements.length > 0) {
        const element = pendingElements.pop();
        if (!element) {
            continue;
        }
        applyNonceIfMissing(element, getNonce);
        let childElement = element.lastElementChild;
        while (childElement) {
            pendingElements.push(childElement);
            childElement = childElement.previousElementSibling;
        }
    }
};

const traverseAndApplyNonce = (root: Node, getNonce: () => string | null): void => {
    if (root instanceof Element) {
        applyNonceInElementSubtree(root, getNonce);
        return;
    }
    if (isDocumentFragment(root)) {
        let childNode = root.lastChild;
        while (childNode) {
            traverseAndApplyNonce(childNode, getNonce);
            childNode = childNode.previousSibling;
        }
    }
};

const initializeCspNonceSupport = (options: { document?: Document } = {}): CspNonceSupportRuntime => {
    const existingRuntime = globalThis.soaiCspNonceSupport;
    if (existingRuntime) {
        return existingRuntime;
    }

    const doc = options.document ?? globalThis.document ?? null;
    if (!doc) {
        return { disconnect: () => {} };
    }

    const getNonce = (): string | null => readNonceFromMeta(doc);
    globalThis.getSoaiCspNonce = getNonce;
    globalThis.soaiCspNonce = getNonce() ?? undefined;

    traverseAndApplyNonce(doc, getNonce);

    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            mutation.addedNodes.forEach((node) => traverseAndApplyNonce(node, getNonce));
        }
    });

    observer.observe(doc.documentElement, { childList: true, subtree: true });

    const runtime: CspNonceSupportRuntime = {
        disconnect(): void {
            observer.disconnect();
        }
    };
    globalThis.soaiCspNonceSupport = runtime;
    return runtime;
};

export { initializeCspNonceSupport };
export type { CspNonceSupportRuntime };
