/* SoAI - Wizard AI setup shared markup [frontend/assets/ts/pages/wizard/rendering/aisetup/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { FREE_API_KEY_LIST_URL } from '@pages/wizard/rendering/view.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';

type AiSetupChipTone = 'ok' | 'caution' | 'warn' | 'fail' | 'neutral' | 'meta' | 'violet';

interface AiSetupChoiceCardOptions {
    type: 'checkbox' | 'radio';
    name: string;
    value: string;
    selected: boolean;
    disabled?: boolean;
    icon: IconName | null;
    title: string;
    titleBadgeMarkup?: string;
    description: string;
    extraMarkup?: string;
    cornerBadgeMarkup?: string;
    className?: string;
    tooltip?: string | null;
}

const renderIcon = (context: WizardViewContext, name: IconName, size: number): string => context.getIconSync(name, { width: size, height: size }).html;

const renderAiSetupHeading = (context: WizardViewContext, heading: string, description: string): string => `<div class="wizard-section-heading"><span class="wizard-eyebrow">${context.sanitizer.html(i18n.t('wizard.aiSetup.eyebrow'))}</span><h2 tabindex="-1">${context.sanitizer.html(heading)}</h2><p>${context.sanitizer.html(description)}</p></div>`;

const renderAiSetupPanelHeading = (context: WizardViewContext, id: string, heading: string, description: string): string => `<div class="wizard-panel-heading"><h4 id="${id}">${context.sanitizer.html(heading)}</h4><p>${context.sanitizer.html(description)}</p></div>`;

const renderFreeApiKeyLink = (context: WizardViewContext): string => {
    const label = context.sanitizer.html(i18n.t('wizard.aiSetup.freeApiKey.label'));
    const accessibleName = context.sanitizer.attribute(i18n.t('wizard.aiSetup.freeApiKey.accessibleName'));
    return `<small class="wizard-field-hint wizard-ai-free-key"><a class="external-link-confirmation" href="${FREE_API_KEY_LIST_URL}" data-href="${FREE_API_KEY_LIST_URL}" target="_blank" rel="noopener noreferrer" aria-label="${accessibleName}" data-tooltip="${accessibleName}"><span>${label}</span>${renderIcon(context, 'external-link', 14)}</a></small>`;
};

const renderAiSetupChip = (context: WizardViewContext, tone: AiSetupChipTone, text: string, options: { icon?: IconName; tooltip?: string | null } = {}): string => {
    const tooltip = options.tooltip ? ` data-tooltip="${context.sanitizer.attribute(options.tooltip)}" tabindex="0"` : '';
    const icon = options.icon ? `<span class="variant-check-badge-icon" aria-hidden="true">${renderIcon(context, options.icon, 14)}</span>` : '';
    return `<span class="variant-check-badge variant-check-badge--${tone}"${tooltip}>${icon}<span class="variant-check-badge-text">${context.sanitizer.html(text)}</span></span>`;
};

const renderAiSetupChips = (chips: readonly string[]): string => (chips.length === 0 ? '' : `<span class="wizard-ai-chips" data-page-scope="models">${chips.join('')}</span>`);

const renderAiSetupChoiceCard = (context: WizardViewContext, options: AiSetupChoiceCardOptions): string => {
    const classes = ['wizard-choice-card', 'wizard-ai-choice', options.className ?? '', options.selected ? 'is-selected' : '', options.disabled === true ? 'is-disabled' : ''].filter(Boolean).join(' ');
    const disabled = options.disabled === true ? ' disabled aria-disabled="true"' : '';
    const tooltip = options.tooltip ? ` data-tooltip="${context.sanitizer.attribute(options.tooltip)}"` : '';
    const icon = options.icon === null ? '' : `<span class="wizard-ai-choice-icon" aria-hidden="true">${renderIcon(context, options.icon, 32)}</span>`;
    return `<label class="${classes}"${tooltip}><input type="${options.type}" name="${context.sanitizer.attribute(options.name)}" value="${context.sanitizer.attribute(options.value)}"${options.selected ? ' checked' : ''}${disabled}><span class="wizard-choice-orb"></span><span class="wizard-ai-choice-body">${icon}<span class="wizard-ai-choice-text"><span class="wizard-ai-choice-title">${options.titleBadgeMarkup ?? ''}<strong>${context.sanitizer.html(options.title)}</strong></span><small>${context.sanitizer.html(options.description)}</small>${options.extraMarkup ?? ''}</span></span>${options.cornerBadgeMarkup ?? ''}</label>`;
};

const renderAiSetupLoadFailedStep = (context: WizardViewContext): string => {
    const retry = context.sanitizer.html(i18n.t('wizard.aiSetup.loadFailed.retry'));
    return `<div class="wizard-step wizard-step--ai" role="alert">${renderAiSetupHeading(context, i18n.t('wizard.aiSetup.loadFailed.title'), i18n.t('wizard.aiSetup.loadFailed.description'))}<div class="wizard-ai-form-actions"><button type="button" class="ui-button ui-variant-accent" data-action="wizard-ai-retry-load" aria-label="${retry}" data-tooltip="${retry}">${retry}</button></div></div>`;
};

const renderAiSetupHint = (context: WizardViewContext, icon: IconName, text: string): string => `<small class="form-disclaimer wizard-field-hint wizard-ai-hint">${renderIcon(context, icon, 14)}<span>${context.sanitizer.html(text)}</span></small>`;

export { renderAiSetupChip, renderAiSetupChips, renderAiSetupChoiceCard, renderAiSetupHeading, renderAiSetupHint, renderAiSetupLoadFailedStep, renderAiSetupPanelHeading, renderFreeApiKeyLink, renderIcon };
export type { AiSetupChipTone, AiSetupChoiceCardOptions };
