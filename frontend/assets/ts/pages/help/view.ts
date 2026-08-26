/* SoAI - Help page rendering [frontend/assets/ts/pages/help/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { SOAI_WEBSITE_URL } from '@core/ui/branding/pageBranding.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderHelpContent } from '@pages/help/rendering/service.ts';
import type { GenerateStandardHeaderFunctionValue } from '@pages/help/rendering/types.ts';

type GetIconSyncFunctionValue = (iconName: IconName, options?: IconOptions) => TrustedHtml;

export const renderHelpPageView = (dependencies: { generateStandardHeader: GenerateStandardHeaderFunctionValue; getIconSync: GetIconSyncFunctionValue }): TrustedHtml => {
    const documentationLabel = i18n.t('help.documentationUrl');
    const documentationIcon = dependencies.getIconSync('book-open', { size: 14, strokeWidth: 1.5 });
    const header = dependencies.generateStandardHeader({
        title: i18n.t('help.title'),
        description: i18n.t('help.description'),
        floating: true,
        contentAreaClass: 'help-content',
        actions: [
            {
                type: 'button',
                content: uiHtml`${documentationIcon}<span>${documentationLabel}</span>`,
                variant: 'ui-variant-neutral',
                class: 'external-link-confirmation',
                attributes: {
                    'data-href': `${SOAI_WEBSITE_URL}/documentation`,
                    'data-external-link-type': 'about-documentation'
                },
                ariaLabel: documentationLabel
            }
        ]
    });
    return toTrustedUiHtml(header.html.replace('<!-- Page content goes here -->', renderHelpContent()));
};
