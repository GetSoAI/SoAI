/* SoAI - Comparison stream request identity [frontend/assets/ts/features/chat/chatstreamservice/comparisonRequestIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const buildComparisonVariantRequestId = (baseRequestId: string, variantIndex: number): string => {
    const normalizedBase = typeof baseRequestId === 'string' ? baseRequestId.trim() : '';
    if (!normalizedBase) throw new Error('Comparison stream requires a base request id.');
    if (!Number.isFinite(variantIndex) || !Number.isInteger(variantIndex) || variantIndex < 0) {
        throw new Error('Comparison stream requires a non-negative variant index.');
    }
    return `${normalizedBase}:variant:${String(variantIndex)}`;
};

const resolveComparisonGroupRequestId = (requestId: string): string => {
    const normalizedRequestId = typeof requestId === 'string' ? requestId.trim() : '';
    if (!normalizedRequestId) return '';
    const suffix = ':variant:';
    const suffixIndex = normalizedRequestId.lastIndexOf(suffix);
    if (suffixIndex < 1) return normalizedRequestId;
    const variantIndexText = normalizedRequestId.slice(suffixIndex + suffix.length);
    if (!/^\d+$/.test(variantIndexText)) return normalizedRequestId;
    return normalizedRequestId.slice(0, suffixIndex);
};

export { buildComparisonVariantRequestId, resolveComparisonGroupRequestId };
