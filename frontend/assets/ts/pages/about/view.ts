/* SoAI - About page rendering [frontend/assets/ts/pages/about/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { SOAI_WEBSITE_URL } from '@core/ui/branding/pageBranding.ts';
import { buildExternalLinkTriggerAttributes } from '@core/ui/externallinks/externalLinkTriggerAttributes.ts';
import { ABOUT_ACTION_SHOW_CREDITS, ABOUT_ACTION_SHOW_LICENSE } from '@pages/about/actions.ts';

interface ExternalLinkConfig {
    className: string;
    attributes: Readonly<Record<string, string>>;
    dataset: Readonly<Record<string, string>>;
}

const EXTERNAL_LINK_BASE_CONFIG: Readonly<Omit<ExternalLinkConfig, 'dataset'>> = Object.freeze({
    className: 'ui-button external-link-confirmation',
    attributes: Object.freeze({ type: 'button' })
});

const buildExternalLinkAttributes = (href: string, linkType: 'about-website' | 'about-documentation'): string => {
    return buildExternalLinkTriggerAttributes({
        ...EXTERNAL_LINK_BASE_CONFIG,
        dataset: { href, externalLinkType: linkType }
    });
};

const renderMetaInfo = (): string => {
    const renderRow = (label: string, valueMarkup: string): string => `<div class="meta-item"><span class="meta-label">${label}</span>${valueMarkup}</div>`;

    const versionRow = renderRow(i18n.t('about.version'), `<span class="meta-value" id="version-display">${i18n.t('about.loading')}</span>`);
    const platformRow = renderRow(i18n.t('about.platform'), `<span class="meta-value" id="platform-display">${i18n.t('about.loading')}</span>`);
    const licenseLabel = i18n.t('about.viewLicense');
    const licenseButton = `<button id="license-button" data-action="${ABOUT_ACTION_SHOW_LICENSE}" class="ui-button ui-button--sm" type="button" aria-label="${licenseLabel}" data-tooltip="${licenseLabel}">${licenseLabel}</button>`;
    const licenseRow = renderRow(i18n.t('about.license'), licenseButton);

    return `<div class="meta-info">${versionRow}${platformRow}${licenseRow}</div>`;
};

const renderWebsiteButtons = (): string => {
    const websiteAttributes = buildExternalLinkAttributes(SOAI_WEBSITE_URL, 'about-website');
    const documentationAttributes = buildExternalLinkAttributes(`${SOAI_WEBSITE_URL}/documentation`, 'about-documentation');
    const websiteLabel = i18n.t('about.websiteUrl');
    const documentationLabel = i18n.t('about.documentationUrl');
    const creditsLabel = i18n.t('about.credits');
    return `
        <div class="website-link">
            <button type="button" ${websiteAttributes} aria-label="${websiteLabel}" data-tooltip="${websiteLabel}">${websiteLabel}</button>
            <button type="button" ${documentationAttributes} aria-label="${documentationLabel}" data-tooltip="${documentationLabel}">${documentationLabel}</button>
            <button id="about-acknowledgments-button" data-action="${ABOUT_ACTION_SHOW_CREDITS}" class="ui-button" type="button" aria-label="${creditsLabel}" data-tooltip="${creditsLabel}">${creditsLabel}</button>
        </div>
    `.trim();
};

export const renderAboutPageView = (): string => {
    return `
        <div id="about-root" class="about-container page-scrollable" data-section="about" data-page-transition-surface="true">
            <div class="about-hero-background">
                <div class="about-pattern"></div>
                <div class="logo-glow"></div>
            </div>
            <div class="about-content-wrapper">
                <div class="about-logo-section">
                    <img src="" alt="${i18n.t('about.logoAlt')}" class="logo logo-ui logo-ui-about" data-logo-type="ui">
                </div>
                <div class="about-main-content">
                    <div class="about-tagline">${i18n.t('about.tagline')}</div>
                    <div class="about-description">
                        <p>${i18n.t('about.description')}</p>
                        ${renderWebsiteButtons()}
                        ${renderMetaInfo()}
                    </div>
                </div>
            </div>
        </div>
    `.trim();
};
