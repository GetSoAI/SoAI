/* SoAI - Shared UI page branding [frontend/assets/ts/core/ui/branding/pageBranding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBranding } from '@core/branding/public.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';

export const SOAI_WEBSITE_URL = 'https://soai.to';

export const applyLogoBranding = (pageDom: Pick<PageDom, 'addClass'> | null, element: Element | null, logoType: string = 'ui'): void => {
    if (!pageDom || !element) {
        return;
    }
    const requestAnimationFrame = getRequestAnimationFrame();
    pageDom.addClass(element, 'logo-transition');
    getBranding().updateLogoElement(element, logoType);
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            pageDom.addClass(element, 'animate-entrance');
        });
    });
};
