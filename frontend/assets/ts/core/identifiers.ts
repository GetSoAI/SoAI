/* SoAI - Shared identifier primitives [frontend/assets/ts/core/identifiers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const sanitizeForId = (value: string): string => {
    const normalized = value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    if (!normalized) {
        throw new Error('Identifier value must produce a non-empty token');
    }
    return normalized;
};

const encodeSegment = (value: string): string => encodeURIComponent(value);

export { sanitizeForId, encodeSegment };
