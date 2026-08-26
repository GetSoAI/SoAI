/* SoAI - Shared animations prefers reduced motion [frontend/assets/ts/core/animations/prefersReducedMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const prefersReducedMotion = (element: Element): boolean => {
    const view = element.ownerDocument.defaultView;
    if (!view || typeof view.matchMedia !== 'function') {
        return false;
    }
    return view.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

export { prefersReducedMotion };
