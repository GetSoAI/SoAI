/* SoAI - Forbidden page DOM contracts [frontend/assets/ts/pages/forbidden/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ForbiddenUi {
    root: HTMLElement;
}

const optionalForbiddenRoot = (host: { optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null }): HTMLElement | null => {
    return host.optionalHTMLElement('#forbidden-root');
};

const requireForbiddenUi = (host: { requireHTMLElement: (selector: string, context?: Element) => HTMLElement }): ForbiddenUi => {
    const root = host.requireHTMLElement('#forbidden-root');
    return { root };
};

export { optionalForbiddenRoot, requireForbiddenUi };
export type { ForbiddenUi };
