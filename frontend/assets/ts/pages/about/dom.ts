/* SoAI - About page DOM contracts [frontend/assets/ts/pages/about/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AboutUiRefs } from '@pages/about/types.ts';

interface AboutDomHost {
    requireHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement;
    optionalHTMLElement: (selector: string, context?: Element | undefined) => HTMLElement | null;
}

export const requireAboutRoot = (host: AboutDomHost): HTMLElement => host.requireHTMLElement('#about-root');
export const requireAboutLogo = (host: AboutDomHost): HTMLElement => host.requireHTMLElement('.logo-ui-about');
export const requireAboutVersion = (host: AboutDomHost): HTMLElement => host.requireHTMLElement('#version-display');
export const requireAboutPlatform = (host: AboutDomHost): HTMLElement => host.requireHTMLElement('#platform-display');

export const optionalAboutLogoSection = (host: AboutDomHost): HTMLElement | null => host.optionalHTMLElement('.about-logo-section');

export const requireAboutUi = (host: AboutDomHost): AboutUiRefs => {
    return {
        root: requireAboutRoot(host),
        logo: requireAboutLogo(host),
        version: requireAboutVersion(host),
        platform: requireAboutPlatform(host)
    };
};
