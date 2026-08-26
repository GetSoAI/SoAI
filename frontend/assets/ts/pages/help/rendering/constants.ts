/* SoAI - Help page rendering constants [frontend/assets/ts/pages/help/rendering/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SOAI_WEBSITE_URL } from '@core/ui/branding/pageBranding.ts';

const EXTERNAL_LINK_CONFIG = Object.freeze({
    className: 'ui-button external-link-confirmation',
    attributes: Object.freeze({ type: 'button' }),
    dataset: Object.freeze({
        href: SOAI_WEBSITE_URL,
        externalLinkType: 'help-website'
    })
});

export { EXTERNAL_LINK_CONFIG };
