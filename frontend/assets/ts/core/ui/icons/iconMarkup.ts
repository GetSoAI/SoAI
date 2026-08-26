/* SoAI - Shared UI icon markup [frontend/assets/ts/core/ui/icons/iconMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export const normalizeSvgMarkup = (svgMarkup: string): string => {
    const normalizedLineEndings = svgMarkup.replace(/\r\n?/gu, '\n');
    const withoutXmlDeclaration = normalizedLineEndings.replace(/^\uFEFF?\s*<\?xml[\s\S]*?\?>\s*/iu, '');
    const withoutDocumentType = withoutXmlDeclaration.replace(/^\s*<!DOCTYPE[\s\S]*?>\s*/iu, '');
    const normalized = withoutDocumentType.trim();
    if (!normalized.startsWith('<svg')) {
        throw new Error('Icon markup must start with <svg');
    }
    return normalized;
};
