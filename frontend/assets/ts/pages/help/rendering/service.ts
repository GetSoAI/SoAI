/* SoAI - Help page rendering service [frontend/assets/ts/pages/help/rendering/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderStructuredTextSection } from '@core/richtextrenderer/structuredSections.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { buildExternalLinkTriggerAttributes } from '@core/ui/externallinks/externalLinkTriggerAttributes.ts';
import { HELP_SECTIONS } from '@features/help/public.ts';
import { HELP_ACTION_NAVIGATE_ABOUT } from '@pages/help/actions.ts';
import { EXTERNAL_LINK_CONFIG } from '@pages/help/rendering/constants.ts';

const renderHelpHero = (): string => {
    const attributes = buildExternalLinkTriggerAttributes(EXTERNAL_LINK_CONFIG);
    const websiteUrl = i18n.t('help.websiteUrl');
    return `
        <div class="help-logo-box">
            <img src="" alt="${i18n.t('help.logoAlt')}" class="logo logo-ui logo-ui-help" data-logo-type="ui">
            <button type="button" ${attributes} ${renderLabelAttributes(websiteUrl)}>${websiteUrl}</button>
        </div>
    `.trim();
};

const renderHelpIntro = (): string => {
    const aboutLabel = i18n.t('help.intro.aboutButton');
    return `
        <div class="help-intro">
            <p>${i18n.t('help.intro.paragraph1')}</p>
            <p>${i18n.t('help.intro.paragraph2')}</p>
            <div class="help-actions">
                <button id="goto-about-page" data-action="${HELP_ACTION_NAVIGATE_ABOUT}" class="ui-button ui-variant-accent" type="button" ${renderLabelAttributes(aboutLabel)}>${aboutLabel}</button>
            </div>
        </div>
    `.trim();
};

const renderHelpContent = (): string => {
    return `
        <div id="help-root" class="help-root">
            ${[
                renderHelpHero(),
                renderHelpIntro(),
                ...HELP_SECTIONS.map(
                    (section) =>
                        renderStructuredTextSection(section, {
                            idPrefix: 'help-section-',
                            sectionClassName: 'help-section rich-text-section',
                            titleClassName: 'help-section-title rich-text-section-title'
                        }).html
                )
            ].join('')}
        </div>
    `.trim();
};

export { renderHelpContent };
