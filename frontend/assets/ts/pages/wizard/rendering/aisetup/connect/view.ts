/* SoAI - Wizard AI setup provider and engine view [frontend/assets/ts/pages/wizard/rendering/aisetup/connect/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderRequiredFieldLabelHtml } from '@core/ui/forms/requiredMarker.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import type { AiSetupConnectView, AiSetupEngineChoiceView } from '@pages/wizard/contracts/aisetup/types.ts';
import { renderAiSetupChip, renderAiSetupChips, renderAiSetupChoiceCard, renderAiSetupHeading, renderAiSetupHint, renderAiSetupPanelHeading } from '@pages/wizard/rendering/aisetup/view.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';

const AI_PROVIDER_FORM_ID = 'wizard-ai-provider-form';
const AI_ENGINE_MODE_INPUT_NAME = 'wizard-ai-engine-mode';
const AI_ENGINE_INPUT_NAME = 'wizard-ai-engine';

const renderTextField = (context: WizardViewContext, options: { id: string; name: string; label: string; value: string; placeholder: string; required: boolean; type?: string; autocomplete?: string }): string => {
    const label = options.required ? renderRequiredFieldLabelHtml(options.label) : context.sanitizer.html(options.label);
    return `<div class="wizard-form-group"><label for="${options.id}">${label}</label><input dir="${options.type === 'url' ? 'ltr' : 'auto'}" id="${options.id}" name="${options.name}" type="${options.type ?? 'text'}" class="wizard-form-input form-input" value="${context.sanitizer.attribute(options.value)}" placeholder="${context.sanitizer.attribute(options.placeholder)}" autocomplete="${options.autocomplete ?? 'off'}" spellcheck="false"${options.required ? ' required' : ''}></div>`;
};

const renderPluginField = (context: WizardViewContext, view: AiSetupConnectView): string => {
    const plugins = view.providerAvailability.operational;
    const draftPlugin = view.connection.draft.pluginName || (plugins[0]?.name ?? '');
    if (plugins.length === 1) return `<input type="hidden" name="plugin" value="${context.sanitizer.attribute(plugins[0]?.name ?? '')}">`;
    const options = plugins.map((plugin) => {
        const name = plugin.name ?? '';
        return `<option value="${context.sanitizer.attribute(name)}"${name === draftPlugin ? ' selected' : ''}>${context.sanitizer.html(plugin.displayName || name)}</option>`;
    });
    const select = `<select id="wizard-ai-provider-plugin" name="plugin" class="form-input" required><option value="">${context.sanitizer.html(i18n.t('models.modal.addProvider.pluginPlaceholder'))}</option>${options.join('')}</select>`;
    return `<div class="wizard-form-group"><label for="wizard-ai-provider-plugin">${renderRequiredFieldLabelHtml(i18n.t('models.modal.addProvider.pluginLabel'))}</label>${renderStandardDropdownSelectControl(select)}</div>`;
};

const renderProviderForm = (context: WizardViewContext, view: AiSetupConnectView): string => {
    const draft = view.connection.draft;
    const keyInput = `<input dir="ltr" id="wizard-ai-provider-key" name="api-key" type="${resolveSecretInputType()}" class="wizard-form-input form-input secret-input" autocomplete="off" spellcheck="false" placeholder="${context.sanitizer.attribute(i18n.t('models.modal.addProvider.apiKeyPlaceholder'))}">`;
    const keyField = `<div class="wizard-form-group"><label for="wizard-ai-provider-key">${context.sanitizer.html(i18n.t('models.modal.addProvider.apiKeyLabel'))}</label>${renderSecretInputControl({ inputId: 'wizard-ai-provider-key', inputMarkup: keyInput })}</div>`;
    const filterField = renderTextField(context, { id: 'wizard-ai-provider-filter', name: 'models-filter', label: i18n.t('wizard.aiSetup.connect.cloud.modelFilter'), value: draft.modelsFilter, placeholder: i18n.t('models.modal.addProvider.modelsFilterPlaceholder'), required: false });
    const error = view.connection.error;
    const connectLabel = context.sanitizer.html(i18n.t('wizard.aiSetup.connect.cloud.connect'));
    return `<form id="${AI_PROVIDER_FORM_ID}" class="wizard-form wizard-ai-provider-form" novalidate>${renderPluginField(context, view)}${renderTextField(context, { id: 'wizard-ai-provider-name', name: 'provider-name', label: i18n.t('models.modal.addProvider.nameLabel'), value: draft.name, placeholder: i18n.t('models.modal.addProvider.nameHelp'), required: true })}${renderTextField(context, { id: 'wizard-ai-provider-url', name: 'api-url', label: i18n.t('models.modal.addProvider.apiUrlLabel'), value: draft.apiUrl, placeholder: i18n.t('models.modal.addProvider.apiUrlPlaceholder'), required: true, type: 'url' })}${keyField}<div class="ui-operation-progress-list wizard-ai-connect-progress" data-ai-cloud-progress></div><div class="wizard-error${error === null ? ' u-hidden' : ''}" role="alert" data-ai-cloud-error>${context.sanitizer.html(error?.message ?? '')}</div><div class="wizard-ai-form-actions"><button type="submit" class="ui-button ui-variant-accent" data-ai-connect aria-label="${connectLabel}" data-tooltip="${connectLabel}">${connectLabel}</button></div><details class="wizard-disclosure"><summary>${context.sanitizer.html(i18n.t('wizard.aiSetup.connect.cloud.moreOptions'))}</summary><div class="wizard-disclosure-body">${filterField}</div></details></form>`;
};

const renderConnectedSummary = (context: WizardViewContext, view: AiSetupConnectView): string => {
    const provider = view.provider;
    if (provider === null) return '';
    const status = i18n.plural('wizard.aiSetup.connect.cloud.connected', view.providerModelCount, { count: view.providerModelCount });
    const changeLabel = context.sanitizer.html(i18n.t('wizard.aiSetup.connect.cloud.change'));
    return `<div class="wizard-ai-connected"><span class="wizard-ai-connected-name">${context.sanitizer.html(provider.providerName)}</span>${renderAiSetupChips([renderAiSetupChip(context, 'ok', status, { icon: 'check' })])}<button type="button" class="ui-button ui-button--sm ui-variant-neutral" data-action="wizard-ai-change-provider" aria-label="${changeLabel}" data-tooltip="${changeLabel}">${changeLabel}</button></div>`;
};

type CloudRegionMode = 'unavailable' | 'summary' | 'form';

const resolveCloudRegionMode = (view: AiSetupConnectView): CloudRegionMode => {
    if (view.providerAvailability.unavailableReason !== null) return 'unavailable';
    return view.provider !== null && !view.connection.editing ? 'summary' : 'form';
};

const renderCloudRegion = (context: WizardViewContext, view: AiSetupConnectView): string => {
    const mode = resolveCloudRegionMode(view);
    if (mode === 'unavailable') return renderAiSetupHint(context, 'warning', view.providerAvailability.unavailableReason ?? '');
    return mode === 'summary' ? renderConnectedSummary(context, view) : renderProviderForm(context, view);
};

const renderEngineChip = (context: WizardViewContext, engine: AiSetupEngineChoiceView): string => {
    if (engine.status === 'installed') return renderAiSetupChip(context, 'ok', i18n.t('wizard.aiSetup.connect.local.status.installed'));
    if (engine.status === 'recommended') return renderAiSetupChip(context, 'ok', i18n.t('wizard.aiSetup.connect.local.status.recommended'));
    if (engine.status === 'warning') return renderAiSetupChip(context, 'warn', i18n.t('wizard.aiSetup.connect.local.status.warning'), { icon: 'warning', tooltip: engine.reason });
    if (engine.status === 'unavailable') return renderAiSetupChip(context, 'fail', i18n.t('wizard.aiSetup.connect.local.status.unavailable'));
    return '';
};

const renderEngineCard = (context: WizardViewContext, engine: AiSetupEngineChoiceView): string =>
    renderAiSetupChoiceCard(context, {
        type: 'checkbox',
        name: AI_ENGINE_INPUT_NAME,
        value: engine.pluginName,
        selected: engine.selected,
        disabled: engine.status === 'unavailable',
        icon: null,
        title: engine.name,
        description: engine.reason ?? '',
        extraMarkup: renderAiSetupChips([renderEngineChip(context, engine)].filter(Boolean)),
        className: 'wizard-ai-engine-card'
    });

const renderLocalSection = (context: WizardViewContext, view: AiSetupConnectView): string => {
    const automatic = renderAiSetupChoiceCard(context, {
        type: 'radio',
        name: AI_ENGINE_MODE_INPUT_NAME,
        value: 'automatic',
        selected: view.engineMode === 'automatic' && view.automaticLine !== null,
        disabled: view.automaticLine === null,
        icon: 'automatic',
        title: i18n.t('wizard.aiSetup.connect.local.automatic'),
        description: view.automaticLine ?? i18n.t('wizard.aiSetup.limited.noCompatibleEngine'),
        className: 'wizard-ai-engine-card'
    });
    const engines = view.engines.map((engine) => renderEngineCard(context, engine)).join('');
    const manualOpen = view.engineMode === 'manual' ? ' open' : '';
    return `<section class="wizard-ai-section" aria-labelledby="wizard-ai-local-title">${renderAiSetupPanelHeading(context, 'wizard-ai-local-title', i18n.t('wizard.aiSetup.connect.local.heading'), i18n.t('wizard.aiSetup.connect.local.description'))}<div class="wizard-ai-stack" role="radiogroup" aria-labelledby="wizard-ai-local-title">${automatic}</div><details class="wizard-disclosure"${manualOpen}><summary>${context.sanitizer.html(i18n.t('wizard.aiSetup.connect.local.chooseManually'))}</summary><div class="wizard-disclosure-body wizard-ai-stack" role="group" aria-label="${context.sanitizer.attribute(i18n.t('wizard.aiSetup.connect.local.chooseManually'))}">${engines}</div></details></section>`;
};

const renderAiConnectStep = (context: WizardViewContext, view: AiSetupConnectView): string => {
    const cloud = view.showCloud ? `<section class="wizard-ai-section" aria-labelledby="wizard-ai-cloud-title">${renderAiSetupPanelHeading(context, 'wizard-ai-cloud-title', i18n.t('wizard.aiSetup.connect.cloud.heading'), i18n.t('wizard.aiSetup.connect.cloud.description'))}<div class="wizard-ai-region" data-ai-region="cloud" data-ai-mode="${resolveCloudRegionMode(view)}">${renderCloudRegion(context, view)}</div></section>` : '';
    const local = view.showLocal ? renderLocalSection(context, view) : '';
    return `<div class="wizard-step wizard-step--ai">${renderAiSetupHeading(context, i18n.t('wizard.aiSetup.connect.heading'), i18n.t('wizard.aiSetup.connect.description'))}${cloud}${local}</div>`;
};

export { AI_ENGINE_INPUT_NAME, AI_ENGINE_MODE_INPUT_NAME, AI_PROVIDER_FORM_ID, renderAiConnectStep, renderCloudRegion, resolveCloudRegionMode };
