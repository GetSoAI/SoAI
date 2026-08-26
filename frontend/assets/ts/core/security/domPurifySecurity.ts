/* SoAI - DOMPurify sanitization policy and hooks [frontend/assets/ts/core/security/domPurifySecurity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import createDOMPurify from 'dompurify';
import { sanitizeImageSource, sanitizeUrl } from '@core/security/urlSanitizer.ts';

const DISALLOWED_ELEMENTS: ReadonlySet<string> = new Set(['script', 'iframe', 'object', 'embed', 'link', 'meta', 'base']);
const URL_ATTRIBUTES: ReadonlySet<string> = new Set(['href', 'src', 'xlink:href', 'poster', 'action', 'formaction']);

const ensureAnchorRelSafety = (element: Element): void => {
    if (!element || element.tagName.toLowerCase() !== 'a') {
        return;
    }
    const target = element.getAttribute('target');
    if (!target || target.toLowerCase() !== '_blank') {
        return;
    }
    const relTokens = new Set(
        (element.getAttribute('rel') || '')
            .split(/\s+/)
            .map((token) => token.trim().toLowerCase())
            .filter(Boolean)
    );
    relTokens.add('noopener');
    relTokens.add('noreferrer');
    element.setAttribute('rel', Array.from(relTokens).join(' '));
};

const sanitizeSrcset = (srcsetValue: string): string | null => {
    if (!srcsetValue) {
        return null;
    }
    const parts = srcsetValue
        .split(',')
        .map((entry) => entry.trim())
        .filter(Boolean);
    if (!parts.length) {
        return null;
    }
    const sanitized: string[] = [];
    for (const entry of parts) {
        const [rawUrl, ...rest] = entry.split(/\s+/).filter(Boolean);
        if (!rawUrl) {
            continue;
        }
        const safeUrl = sanitizeImageSource(rawUrl);
        if (!safeUrl) {
            continue;
        }
        sanitized.push([safeUrl, ...rest].join(' '));
    }
    return sanitized.length ? sanitized.join(', ') : null;
};

const sanitizeStyleText = (cssText: string): string => {
    const normalized = cssText.replace(/\0/g, '');
    const lower = normalized.toLowerCase();

    if (lower.includes('javascript:')) return '';
    if (lower.includes('vbscript:')) return '';
    if (/@import\b/i.test(normalized)) return '';
    if (/expression\s*\(/i.test(normalized)) return '';
    if (/url\(\s*(['"])?(?!#)/i.test(normalized)) return '';

    return normalized;
};

type DOMPurifyInstance = ReturnType<typeof createDOMPurify>;
type PurifierWindow = NonNullable<Parameters<typeof createDOMPurify>[0]>;

interface PurifierWindowCandidate {
    DocumentFragment?: typeof DocumentFragment;
    HTMLTemplateElement?: typeof HTMLTemplateElement;
    Node?: typeof Node;
    Element?: typeof Element;
    NodeFilter?: typeof NodeFilter;
    NamedNodeMap?: typeof NamedNodeMap;
    HTMLFormElement?: typeof HTMLFormElement;
    DOMParser?: typeof DOMParser;
}

interface CachedPurifier {
    purify: DOMPurifyInstance;
    hooksApplied: boolean;
}

const purifierCache = new WeakMap<PurifierWindow, CachedPurifier>();

const isPurifierWindowCandidate = <T>(value: T): value is T & PurifierWindowCandidate => typeof value === 'object' && value !== null;

const isPurifierWindow = <T>(value: T): value is T & PurifierWindow => {
    if (!isPurifierWindowCandidate(value)) {
        return false;
    }

    const requiredConstructors: readonly (keyof PurifierWindowCandidate)[] = ['DocumentFragment', 'HTMLTemplateElement', 'Node', 'Element', 'NodeFilter', 'NamedNodeMap', 'HTMLFormElement', 'DOMParser'];

    for (const key of requiredConstructors) {
        if (typeof value[key] !== 'function') {
            return false;
        }
    }

    return true;
};

const getPurifier = (windowRef: PurifierWindow): DOMPurifyInstance => {
    const existing = purifierCache.get(windowRef);
    if (existing) {
        if (!existing.hooksApplied) {
            throw new Error('Security purifier cache is corrupted (hooksApplied=false)');
        }
        return existing.purify;
    }

    const purify = createDOMPurify(windowRef);

    purify.addHook('uponSanitizeAttribute', (node, data) => {
        const rawName = String(data.attrName || '');
        const name = rawName.toLowerCase();
        const value = String(data.attrValue || '');

        if (name.startsWith('on') || name === 'srcdoc') {
            data.keepAttr = false;
            return;
        }

        if (name === 'style') {
            const lower = value.toLowerCase();
            if (lower.includes('javascript:') || lower.includes('vbscript:') || /expression\s*\(/.test(lower)) {
                data.keepAttr = false;
            }
            return;
        }

        if (name === 'srcset') {
            const safe = sanitizeSrcset(value);
            if (!safe) {
                data.keepAttr = false;
                return;
            }
            data.attrValue = safe;
            return;
        }

        if (URL_ATTRIBUTES.has(name)) {
            const tag = node instanceof Element ? node.tagName.toLowerCase() : '';
            const safeUrl = name === 'src' && tag === 'img' ? sanitizeImageSource(value) : sanitizeUrl(value, { allowRelative: true, allowBlob: true });
            if (!safeUrl) {
                data.keepAttr = false;
                return;
            }
            data.attrValue = safeUrl;
        }
    });

    purify.addHook('afterSanitizeAttributes', (node) => {
        if (node instanceof Element) {
            ensureAnchorRelSafety(node);
        }
    });

    purify.addHook('uponSanitizeElement', (node) => {
        if (!(node instanceof Element)) {
            return;
        }
        if (node.tagName.toLowerCase() !== 'style') {
            return;
        }
        const text = node.textContent ?? '';
        if (!text.trim()) {
            return;
        }
        const sanitized = sanitizeStyleText(text);
        node.textContent = sanitized;
    });

    purifierCache.set(windowRef, { purify, hooksApplied: true });
    return purify;
};

const getSecurityPurifierFromDocument = (doc: Document): DOMPurifyInstance | null => {
    const windowRef = doc.defaultView;
    if (!windowRef) {
        return null;
    }
    if (!isPurifierWindow(windowRef)) {
        return null;
    }
    return getPurifier(windowRef);
};

export { DISALLOWED_ELEMENTS, getSecurityPurifierFromDocument };
export type { DOMPurifyInstance };
