/* SoAI - Shared frontend DOM actions mapping [frontend/assets/ts/core/dom/actions/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDomDocument } from '@core/dom/domEnvironment.ts';
import { securityApi } from '@core/security/public.ts';
import { isHTMLCollection, isNode, isNodeList, isNullOrUndefined, isString } from '@core/typeGuards.ts';
import type { DOMChildContent } from '@core/dom/types.ts';

const normalizeDataName = (name = ''): string => {
    if (!name) return '';
    const raw = name.startsWith('data-') ? name.slice(5) : name;
    if (!raw) return '';
    return raw
        .replace(/[_\s]+/g, '-')
        .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
        .replace(/-+/g, '-')
        .replace(/^-+/, '')
        .toLowerCase();
};

const toDatasetKey = (name = ''): string => {
    const normalized = normalizeDataName(name);
    if (!normalized) return '';
    return normalized
        .split('-')
        .filter(Boolean)
        .map((part, index) => (index === 0 ? part : part.charAt(0).toUpperCase() + part.slice(1)))
        .join('');
};

const normalizeChildren = (input: DOMChildContent): Node[] => {
    if (isNullOrUndefined(input)) return [];
    if (Array.isArray(input)) return input.flatMap(normalizeChildren);
    if (isNodeList(input)) return Array.from(input).flatMap(normalizeChildren);
    if (isHTMLCollection(input)) return Array.from(input).flatMap(normalizeChildren);
    if (isNode(input)) return [input];
    if (isString(input)) {
        const sanitized = securityApi.sanitizeText(input, { trim: false });
        if (!sanitized) return [];
        return [getDomDocument().createTextNode(sanitized)];
    }
    return [];
};

const buildFragmentFromNodes = (children: DOMChildContent): DocumentFragment => {
    const fragment = getDomDocument().createDocumentFragment();
    normalizeChildren(children).forEach((node) => fragment.appendChild(node));
    return fragment;
};

export { buildFragmentFromNodes, normalizeChildren, normalizeDataName, toDatasetKey };
