/* SoAI - Wizard page rendering [frontend/assets/ts/pages/wizard/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { AUTH_ROUTE_LOGIN } from '@core/routing/router/authRouteTarget.ts';
import type { WebuiUser } from '@core/auth/types.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { requireLicensingEditionContribution } from '@core/edition/licensingContribution.ts';
import type { WizardStepId } from '@features/wizard/public.ts';
import { renderProductAccessView } from '@pages/wizard/rendering/view.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';
import { presentDeclaration, presentEdition, presentEntitlementType, presentLicensingState } from '@core/licensing/valuePresentation.ts';

const readUsername = (value: WebuiUser | null): string | null => {
    if (!value) {
        return null;
    }
    const trimmed = value.username.trim();
    return trimmed ? trimmed : null;
};

const WIZARD_BRAND_SOAI_MARKUP = '<span class="page-title-so" aria-label="SoAI" data-tooltip="SoAI">SoAI</span>';

const renderWelcomeHeading = (context: WizardViewContext): string => {
    const heading = context.sanitizer.html(requireLicensingEditionContribution().getWelcomeHeading());
    return heading.split('SoAI').join(WIZARD_BRAND_SOAI_MARKUP);
};

const renderCompletionSummary = (context: WizardViewContext): string => {
    const summary: string[] = [];
    const icon = (name: IconName, size: number): string => context.getIconSync(name, { width: size, height: size }).html;

    const username = readUsername(context.state.adminUser);
    if (username) {
        summary.push(`<div class="wizard-summary-item"><div class="wizard-summary-icon">${icon('user', 24)}</div><div><h3>${context.sanitizer.html(i18n.t('wizard.completion.summary.admin.title'))}</h3><p>${context.sanitizer.html(i18n.t('wizard.completion.summary.admin.created'))}</p><p class="wizard-summary-detail">${context.sanitizer.html(i18n.t('wizard.completion.summary.admin.username', { username }))}</p></div></div>`);
    }

    const completed = context.state.completedSummary;
    if (completed === null) return summary.join('');
    const licensingDetails = [presentEdition(completed.edition), presentDeclaration(completed.declaration)];
    if (completed.entitlementType !== null) licensingDetails.push(presentEntitlementType(completed.entitlementType));
    if (completed.perpetual) licensingDetails.push(i18n.t('settings.licensing.perpetual'));
    else if (completed.timeBoundary !== null) licensingDetails.push(i18n.formatDate(new Date(completed.timeBoundary), { dateStyle: 'medium', timeStyle: 'medium' }));
    summary.push(`<div class="wizard-summary-item"><div class="wizard-summary-icon">${icon('key', 24)}</div><div><h3>${context.sanitizer.html(i18n.t('wizard.completion.summary.licensing.title'))}</h3><p>${context.sanitizer.html(presentLicensingState(completed.entitlementStatus))}</p><p class="wizard-summary-detail">${context.sanitizer.html(licensingDetails.join(' · '))}</p></div></div>`);
    const pluginCount = completed.detectedPlugins.length;
    const pluginDetail = i18n.t('wizard.completion.backendNote');
    summary.push(`<div class="wizard-summary-item"><div class="wizard-summary-icon">${icon('plugin', 24)}</div><div><h3>${context.sanitizer.html(i18n.t('wizard.completion.summary.plugins.title'))}</h3><p>${context.sanitizer.html(i18n.plural('wizard.completion.summary.plugins.installed', pluginCount, { count: pluginCount }))}</p><p class="wizard-summary-detail">${context.sanitizer.html(String(pluginDetail))}</p></div></div>`);

    return summary.join('');
};

export const renderWizardShellView = (context: WizardViewContext): string => {
    const total = context.state.totalSteps;
    return `
        <div class="wizard-container page-scrollable" data-section="wizard" data-page-transition-surface="true">
        <div class="wizard-background"><div class="wizard-background-pattern"></div></div>
        <div class="wizard-card">
        <div class="wizard-header">
        <img src="" alt="${i18n.t('wizard.logoAlt')}" class="wizard-logo logo logo-ui logo-transition" data-logo-type="ui">
        <div class="wizard-header-text">
        <h1>${i18n.t('wizard.title')}</h1>
        <div class="wizard-progress">
        <div class="progress-bar"><div class="progress-fill progress-orange"></div></div>
        <span class="wizard-progress-text">${i18n.t('wizard.progress.stepOf', { current: 1, total })}</span>
        </div>
        </div>
        </div>
        <div id="wizard-content" class="wizard-content"></div>
        <div class="wizard-navigation">
        <div class="wizard-nav-left">
        <button type="button" id="wizard-back" data-action="wizard-back" class="wizard-nav-button ui-button ui-variant-neutral u-hidden" aria-label="${i18n.t('wizard.navigation.back')}" data-tooltip="${i18n.t('wizard.navigation.back')}">${i18n.t('wizard.navigation.back')}</button>
        </div>
        <div class="wizard-nav-right">
        <button type="button" id="wizard-next" data-action="wizard-next" class="wizard-nav-button ui-button ui-variant-success" aria-label="${i18n.t('wizard.navigation.getStarted')}" data-tooltip="${i18n.t('wizard.navigation.getStarted')}">${i18n.t('wizard.navigation.getStarted')}</button>
        </div>
        </div>
        </div>
        </div>`;
};

export const renderWizardSuppressedView = (context: WizardViewContext): string => {
    const title = context.sanitizer.html(i18n.t('wizard.suppressed.title'));
    const description = context.sanitizer.html(i18n.t('wizard.suppressed.description'));
    const actionLabel = context.sanitizer.html(i18n.t('wizard.suppressed.action.signIn'));
    const loginHref = context.sanitizer.attribute(`#${AUTH_ROUTE_LOGIN}`);

    return `
        <div class="wizard-container wizard-container--suppressed page-scrollable" data-section="wizard" data-page-transition-surface="true">
        <div class="wizard-background"><div class="wizard-background-pattern"></div></div>
        <div class="wizard-card">
        <div class="wizard-header wizard-header--suppressed">
        <div class="wizard-hero-icon">${context.getIconSync('check', { width: 32, height: 32 }).html}</div>
        <div class="wizard-header-text">
        <h1>${title}</h1>
        <p>${description}</p>
        </div>
        </div>
        <div class="wizard-navigation wizard-navigation--suppressed">
        <div class="wizard-nav-right">
        <a class="wizard-nav-button ui-button ui-variant-accent is-ready" href="${loginHref}">${actionLabel}</a>
        </div>
        </div>
        </div>
        </div>`;
};

export const renderWizardStepView = (stepId: WizardStepId, context: WizardViewContext): string => {
    switch (stepId) {
        case 'welcome': {
            const languageOptionsMarkup = context.languageOptions
                .map((option) => {
                    const value = option.value || '';
                    const label = option.label || value;
                    const selected = value === context.currentLanguage ? ' selected' : '';
                    return `<option value="${context.sanitizer.attribute(String(value))}"${selected}>${context.sanitizer.html(String(label))}</option>`;
                })
                .join('');
            return `
        <div class="wizard-welcome-bg" aria-hidden="true"></div>
        <div class="wizard-step">
        <div class="wizard-hero">
        <div class="wizard-hero-icon wizard-hero-icon--logo"><img src="" alt="${context.sanitizer.attribute(i18n.t('wizard.logoAlt'))}" class="wizard-step-logo logo logo-small logo-transition" data-logo-type="small"></div>
        <h2>${renderWelcomeHeading(context)}</h2>
        <p>${i18n.t('wizard.welcome.description')}</p>
        </div>
        <div class="wizard-language-setting setting-item">
        <div class="setting-info">
        <label class="setting-label" for="language-select">${context.sanitizer.html(i18n.t('settings.preferences.language.label'))}</label>
        <span class="setting-help">${context.sanitizer.html(i18n.t('settings.preferences.language.help'))}</span>
        </div>
        <div class="setting-control">
        ${renderStandardDropdownSelectControl(`<select id="language-select" class="setting-input">${languageOptionsMarkup}</select>`)}
        </div>
        </div>
        </div>`;
        }
        case 'license': {
            const status = context.state.status;
            return `
        <div class="wizard-step wizard-step--license">
        <div class="wizard-section-heading"><span class="wizard-eyebrow">${context.sanitizer.html(requireLicensingEditionContribution().getEditionLabel())}</span><h2>${i18n.t('about.licenseTitle')}</h2><p>${context.sanitizer.html(status?.licenseDocumentName ?? '')}</p></div>
        <textarea id="wizard-license-text" class="wizard-license-textbox" readonly spellcheck="false">${context.sanitizer.html(context.state.licenseText)}</textarea>
        <p class="wizard-document-fingerprint"><span>${i18n.t('wizard.license.fingerprint')}</span><code>${context.sanitizer.html(status?.licenseFingerprint ?? '')}</code></p>
        </div>`;
        }
        case 'use': {
            const selected = context.state.declarationSelection;
            const status = context.state.status;
            const commercialUnavailableTooltip = context.sanitizer.attribute(i18n.t('licensing.base.unavailableTooltip'));
            return `
        <div class="wizard-step wizard-step--use">
        <div class="wizard-section-heading"><span class="wizard-eyebrow">${i18n.t('wizard.use.eyebrow')}</span><h2>${i18n.t('wizard.use.heading')}</h2><p>${i18n.t('wizard.use.description')}</p></div>
        <div class="wizard-use-selection">
        <div class="wizard-choice-grid" role="radiogroup" aria-label="${context.sanitizer.attribute(i18n.t('wizard.use.heading'))}">
        <label class="wizard-choice-card${selected === 'personal' ? ' is-selected' : ''}"><input type="radio" name="wizard-use" value="personal"${selected === 'personal' ? ' checked' : ''}><span class="wizard-choice-orb"></span><span><strong>${i18n.t('wizard.use.personal.title')}</strong><small>${i18n.t('wizard.use.personal.description')}</small></span></label>
        <label class="wizard-choice-card is-disabled${selected === 'organization_commercial' ? ' is-selected' : ''}" tabindex="0" aria-disabled="true" data-tooltip="${commercialUnavailableTooltip}"><input type="radio" name="wizard-use" value="organization_commercial"${selected === 'organization_commercial' ? ' checked' : ''} disabled><span class="wizard-choice-orb"></span><span><strong>${i18n.t('wizard.use.organization.title')}</strong><small>${i18n.t('wizard.use.organization.description')}</small></span></label>
        </div>
        <div class="wizard-attestation-region${selected === 'personal' ? ' is-expanded' : ''}" aria-hidden="${selected === 'personal' ? 'false' : 'true'}"${selected === 'personal' ? '' : ' inert'}><div class="wizard-attestation-region-inner"><label class="wizard-attestation"><input id="wizard-personal-attestation" type="checkbox"${context.state.attestationConfirmed ? ' checked' : ''}${selected === 'personal' ? '' : ' disabled'}><span>${context.sanitizer.html(status?.personalAttestationText ?? '')}</span></label></div></div>
        </div>
        <div class="wizard-error${context.state.inlineError ? '' : ' u-hidden'}" role="alert" data-wizard-licensing-error>${context.sanitizer.html(context.state.inlineError ?? '')}</div>
        </div>`;
        }
        case 'product_access': {
            return renderProductAccessView(context);
        }
        case 'account': {
            const passwordInputType = resolveSecretInputType();
            const passwordInput = `<input id="admin-password" name="password" type="${passwordInputType}" class="wizard-form-input form-input secret-input" minlength="8" autocomplete="new-password" placeholder="${i18n.t('wizard.userCreation.password.placeholder')}" required>`;
            const passwordConfirmInput = `<input id="admin-password-confirm" name="password-confirm" type="${passwordInputType}" class="wizard-form-input form-input secret-input" minlength="8" autocomplete="new-password" placeholder="${i18n.t('wizard.userCreation.confirmPassword.placeholder')}" required>`;
            const passwordFields = `
	            <div class="wizard-password-row">
		        <div class="wizard-form-group">
		        <label for="admin-password">${i18n.t('wizard.userCreation.password.label')}</label>
                ${renderSecretInputControl({ inputId: 'admin-password', inputMarkup: passwordInput })}
		        </div>
		        <div class="wizard-form-group">
		        <label for="admin-password-confirm">${i18n.t('wizard.userCreation.confirmPassword.label')}</label>
                ${renderSecretInputControl({ inputId: 'admin-password-confirm', inputMarkup: passwordConfirmInput })}
		        </div>
	            </div>`;
            return `
			        <div class="wizard-step wizard-step--account">
			        <div class="wizard-hero">
			        <div class="wizard-hero-icon">${context.getIconSync('user', { width: 32, height: 32 }).html}</div>
		        <h2>${i18n.t('wizard.userCreation.heading')}</h2>
	        <p>${i18n.t('wizard.userCreation.description')}</p>
	        </div>
		        <form id="admin-user-form" class="wizard-form">
		        <div id="user-creation-error" class="wizard-error u-hidden" role="alert"></div>
		        <div class="wizard-form-group">
		        <label for="admin-username">${i18n.t('wizard.userCreation.username.label')}</label>
		        <input id="admin-username" name="username" type="text" class="wizard-form-input form-input" minlength="3" maxlength="50" pattern="[a-zA-Z0-9_.\\-]+" autocomplete="username" placeholder="${i18n.t('wizard.userCreation.username.placeholder')}" required>
	        </div>
	        ${passwordFields}
	        </form>
	        </div>`;
        }
        case 'complete': {
            const summary = renderCompletionSummary(context);
            const description = context.state.isSessionActivationRequired ? i18n.t('wizard.completion.signInRequiredDescription') : i18n.t('wizard.completion.description');
            return `
	        <div class="wizard-step wizard-step--complete">
	        <div class="wizard-hero">
	        <div class="wizard-hero-icon">${context.getIconSync('check', { width: 32, height: 32 }).html}</div>
	        <h2>${i18n.t('wizard.completion.heading')}</h2>
        <p>${description}</p>
        </div>
        <div class="wizard-setup-summary">${summary}</div>
        </div>`;
        }
    }
};
