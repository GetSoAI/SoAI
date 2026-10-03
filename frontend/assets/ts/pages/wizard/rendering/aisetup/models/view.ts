/* SoAI - Wizard AI setup model selection view [frontend/assets/ts/pages/wizard/rendering/aisetup/models/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';
import type { AiSetupCloudModelView, AiSetupLocalCardView, AiSetupModelsView, AiSetupPickedModelView } from '@pages/wizard/contracts/aisetup/types.ts';
import { renderAiSetupChip, renderAiSetupChips, renderAiSetupChoiceCard, renderAiSetupHeading, renderAiSetupPanelHeading, renderIcon } from '@pages/wizard/rendering/aisetup/view.ts';
import { renderAiSearchResults, renderAiSearchVariants } from '@pages/wizard/rendering/aisetup/search/view.ts';
import type { ModelCatalogUseCase } from '@pages/wizard/services/aisetup/catalog/constants.ts';
import { REDUCED_CONTEXT_TOKENS, type RecommendationCard, type RecommendationRole, type RecommendationSpeed } from '@pages/wizard/services/aisetup/recommendations/service.ts';
import type { WizardViewContext } from '@pages/wizard/types.ts';

const AI_MODEL_INPUT_NAME = 'wizard-ai-model';
const AI_FIRST_CHAT_INPUT_NAME = 'wizard-ai-first-chat';
const AI_SEARCH_FORM_ID = 'wizard-ai-search-form';
const AI_CLOUD_FILTER_ID = 'wizard-ai-cloud-filter';

const localSelectionKey = (catalogId: string): string => `catalog:${catalogId}`;
const itemSelectionKey = (itemId: string): string => `item:${itemId}`;
const cloudSelectionKey = (modelId: string): string => `cloud:${modelId}`;

const parseSelectionKey = (key: string): { type: string; value: string } => {
    const separator = key.indexOf(':');
    return separator < 0 ? { type: '', value: key } : { type: key.slice(0, separator), value: key.slice(separator + 1) };
};

const readRoleLabel = (role: RecommendationRole): string => {
    switch (role) {
        case 'recommended':
            return i18n.t('wizard.aiSetup.models.role.recommended');
        case 'faster':
            return i18n.t('wizard.aiSetup.models.role.faster');
        case 'smallest':
            return i18n.t('wizard.aiSetup.models.role.smallest');
    }
};

const readSpeedLabel = (speed: RecommendationSpeed): string => {
    switch (speed) {
        case 'fast':
            return i18n.t('wizard.aiSetup.models.speed.fast');
        case 'moderate':
            return i18n.t('wizard.aiSetup.models.speed.moderate');
        case 'slow':
            return i18n.t('wizard.aiSetup.models.speed.slow');
    }
};

const readSpeedTone = (speed: RecommendationSpeed): 'violet' | 'caution' | 'warn' => {
    switch (speed) {
        case 'fast':
            return 'violet';
        case 'moderate':
            return 'caution';
        case 'slow':
            return 'warn';
    }
};

const readUseCaseLabel = (useCase: ModelCatalogUseCase): string => {
    switch (useCase) {
        case 'advanced':
            return i18n.t('wizard.aiSetup.models.useCase.advanced');
        case 'balanced':
            return i18n.t('wizard.aiSetup.models.useCase.balanced');
        case 'reasoning':
            return i18n.t('wizard.aiSetup.models.useCase.reasoning');
        case 'light':
            return i18n.t('wizard.aiSetup.models.useCase.light');
    }
};

const renderOpenChatChoice = (context: WizardViewContext, view: AiSetupModelsView, key: string, itemId: string | null): string => {
    const visible = view.showOpenChat && itemId !== null;
    const checked = itemId !== null && itemId === view.firstChatItemId;
    return `<label class="wizard-ai-open-chat${visible ? '' : ' u-hidden'}" data-ai-open-chat="${context.sanitizer.attribute(key)}"><input type="radio" name="${AI_FIRST_CHAT_INPUT_NAME}" value="${context.sanitizer.attribute(key)}"${checked ? ' checked' : ''}><span>${context.sanitizer.html(i18n.t('wizard.aiSetup.models.openChatWith'))}</span></label>`;
};

const formatParameters = (card: RecommendationCard): string => {
    const total = i18n.formatNumber(card.entry.parametersTotalB);
    if (card.entry.architecture === 'dense') return i18n.t('wizard.aiSetup.models.details.parametersDense', { total });
    return i18n.t('wizard.aiSetup.models.details.parametersMoe', { total, active: i18n.formatNumber(card.entry.parametersActiveB) });
};

const renderDetailRow = (context: WizardViewContext, label: string, valueMarkup: string): string => `<div><dt>${context.sanitizer.html(label)}</dt><dd>${valueMarkup}</dd></div>`;

const renderCardDetails = (context: WizardViewContext, view: AiSetupLocalCardView): string => {
    const { card } = view;
    const tokens = i18n.formatNumber(card.contextTokens);
    const contextText = card.contextTokens === REDUCED_CONTEXT_TOKENS ? i18n.t('wizard.aiSetup.models.details.contextReduced', { tokens }) : i18n.t('wizard.aiSetup.models.details.contextTokens', { tokens });
    const repository = context.sanitizer.html(card.entry.repository);
    const source = view.repositoryUrl === null ? `<span dir="ltr">${repository}</span>` : `<a class="external-link-confirmation" dir="ltr" href="${context.sanitizer.attribute(view.repositoryUrl)}" data-href="${context.sanitizer.attribute(view.repositoryUrl)}" target="_blank" rel="noopener noreferrer">${repository}${renderIcon(context, 'external-link', 12)}</a>`;
    const rows = [renderDetailRow(context, i18n.t('wizard.aiSetup.models.details.quantization'), `<span dir="ltr">${context.sanitizer.html(card.entry.quantization)}</span>`), renderDetailRow(context, i18n.t('wizard.aiSetup.models.details.parameters'), context.sanitizer.html(formatParameters(card))), renderDetailRow(context, i18n.t('wizard.aiSetup.models.details.context'), context.sanitizer.html(contextText)), renderDetailRow(context, i18n.t('wizard.aiSetup.models.details.file'), `<span dir="ltr">${context.sanitizer.html(card.entry.file)}</span>`), renderDetailRow(context, i18n.t('wizard.aiSetup.models.details.source'), source)];
    return `<details class="wizard-disclosure wizard-ai-model-details"><summary>${context.sanitizer.html(i18n.t('wizard.aiSetup.models.details.label'))}</summary><dl class="wizard-disclosure-body wizard-ai-details-list">${rows.join('')}</dl></details>`;
};

const renderLocalCard = (context: WizardViewContext, view: AiSetupModelsView, cardView: AiSetupLocalCardView): string => {
    const { card } = cardView;
    const key = localSelectionKey(card.entry.id);
    const roleBadge = card.role === null ? '' : `<span class="ui-badge ui-badge--compact wizard-ai-role-badge wizard-ai-role-badge--${card.role}">${context.sanitizer.html(readRoleLabel(card.role))}</span>`;
    const chips = renderAiSetupChips([renderAiSetupChip(context, 'meta', i18n.t('wizard.aiSetup.models.downloadSize', { size: formatBytes(card.entry.downloadBytes) }), { icon: 'download' }), card.runsOn === 'gpu' ? renderAiSetupChip(context, 'ok', i18n.t('wizard.aiSetup.models.runsOnGpu'), { icon: 'device-gpu' }) : renderAiSetupChip(context, 'ok', i18n.t('wizard.aiSetup.models.runsOnCpu'), { icon: 'device-cpu' }), renderAiSetupChip(context, readSpeedTone(card.speed), readSpeedLabel(card.speed), { icon: 'clock' })]);
    const choice = renderAiSetupChoiceCard(context, { type: 'checkbox', name: AI_MODEL_INPUT_NAME, value: key, selected: cardView.itemId !== null, icon: null, title: card.entry.name, titleBadgeMarkup: roleBadge, description: readUseCaseLabel(card.entry.useCase), extraMarkup: chips, className: 'wizard-model-card' });
    return `<div class="wizard-ai-model wizard-ai-model--recommended" data-ai-model="${context.sanitizer.attribute(key)}">${choice}${renderCardDetails(context, cardView)}${renderOpenChatChoice(context, view, key, cardView.itemId)}</div>`;
};

const renderPickedModel = (context: WizardViewContext, view: AiSetupModelsView, picked: AiSetupPickedModelView): string => {
    const key = itemSelectionKey(picked.itemId);
    const choice = renderAiSetupChoiceCard(context, { type: 'checkbox', name: AI_MODEL_INPUT_NAME, value: key, selected: true, icon: 'model-default', title: picked.label, description: picked.detail, className: 'wizard-model-card' });
    return `<div class="wizard-ai-model" data-ai-model="${context.sanitizer.attribute(key)}">${choice}${renderOpenChatChoice(context, view, key, picked.itemId)}</div>`;
};

const renderSearchDisclosure = (context: WizardViewContext, view: AiSetupModelsView): string => {
    const searchLabel = context.sanitizer.html(i18n.t('models.modal.addModel.searchLabel'));
    const searchButton = context.sanitizer.html(i18n.t('models.modal.addModel.searchButton'));
    const form = `<form id="${AI_SEARCH_FORM_ID}" class="wizard-ai-search-form" role="search"><label for="wizard-ai-search-input">${searchLabel}</label><div class="wizard-ai-search-row"><div class="searchbar-container searchbar-container--collection"><input id="wizard-ai-search-input" name="query" type="text" class="form-input searchbar-input" value="${context.sanitizer.attribute(view.search.query)}" autocomplete="off" spellcheck="false">${renderSearchFieldActions().html}</div><button type="submit" class="ui-button" aria-label="${searchButton}" data-tooltip="${searchButton}">${searchButton}</button></div></form>`;
    return `<details class="wizard-disclosure" data-ai-search${view.searchOpen ? ' open' : ''}><summary>${context.sanitizer.html(i18n.t('wizard.aiSetup.models.searchAnother'))}</summary><div class="wizard-disclosure-body wizard-ai-search" data-page-scope="models">${form}<div class="wizard-ai-scroll" data-ai-region="search-results" aria-live="polite">${renderAiSearchResults(context, view.search)}</div><div class="wizard-ai-scroll" data-ai-region="search-variants" aria-live="polite">${renderAiSearchVariants(context, view.search)}</div></div></details>`;
};

const renderLimitedState = (context: WizardViewContext, message: string): string => {
    const useCloud = context.sanitizer.html(i18n.t('wizard.aiSetup.limited.useCloud'));
    const searchManually = context.sanitizer.html(i18n.t('wizard.aiSetup.limited.searchManually'));
    const actions = toTrustedUiHtml(`<button type="button" class="ui-button ui-variant-neutral" data-action="wizard-ai-search-manually" aria-label="${searchManually}" data-tooltip="${searchManually}">${searchManually}</button><button type="button" class="ui-button ui-variant-accent" data-action="wizard-ai-use-cloud" aria-label="${useCloud}" data-tooltip="${useCloud}">${useCloud}</button>`);
    return renderEmptyState({ icon: context.getIconSync('warning', { width: 32, height: 32 }), title: message, actions, className: 'ui-empty-state wizard-ai-empty wizard-ai-empty--limited' }).html;
};

const renderAiPickedModels = (context: WizardViewContext, view: AiSetupModelsView): string => view.pickedModels.map((model) => renderPickedModel(context, view, model)).join('');

const renderLocalSection = (context: WizardViewContext, view: AiSetupModelsView): string => {
    const cards = view.localCards.map((card) => renderLocalCard(context, view, card)).join('');
    const picked = `<div class="wizard-ai-contents" data-ai-region="picked">${renderAiPickedModels(context, view)}</div>`;
    const limited = view.limitedMessage === null ? '' : renderLimitedState(context, view.limitedMessage);
    const body = `${limited}<div class="wizard-ai-stack" role="group" aria-labelledby="wizard-ai-local-models-title">${view.limitedMessage === null ? cards : ''}${picked}</div>`;
    return `<section class="wizard-ai-section" aria-labelledby="wizard-ai-local-models-title">${renderAiSetupPanelHeading(context, 'wizard-ai-local-models-title', i18n.t('wizard.aiSetup.models.local.heading'), i18n.t('wizard.aiSetup.models.local.description'))}${body}${renderSearchDisclosure(context, view)}</section>`;
};

const renderCloudModel = (context: WizardViewContext, view: AiSetupModelsView, model: AiSetupCloudModelView): string => {
    const key = cloudSelectionKey(model.modelId);
    const selected = model.itemId !== null;
    return `<div class="wizard-ai-cloud-model" data-ai-model="${context.sanitizer.attribute(key)}" data-ai-filter-text="${context.sanitizer.attribute(`${model.label} ${model.modelId}`.toLowerCase())}"><label class="search-item search-item--card wizard-ai-cloud-choice${selected ? ' is-selected' : ''}"><input type="checkbox" name="${AI_MODEL_INPUT_NAME}" value="${context.sanitizer.attribute(key)}"${selected ? ' checked' : ''}><span class="wizard-choice-orb"></span><span class="search-item-content"><span class="search-item-model" dir="ltr">${context.sanitizer.html(model.label)}</span></span></label>${renderOpenChatChoice(context, view, key, model.itemId)}</div>`;
};

const renderAiCloudModels = (context: WizardViewContext, view: AiSetupModelsView): string => {
    const heading = i18n.t('wizard.aiSetup.models.cloud.heading', { provider: view.providerName ?? '' });
    if (view.cloudModels.length === 0) {
        const back = context.sanitizer.html(i18n.t('wizard.aiSetup.models.cloud.backToProvider'));
        const actions = toTrustedUiHtml(`<button type="button" class="ui-button ui-variant-neutral" data-action="wizard-ai-back-to-provider" aria-label="${back}" data-tooltip="${back}">${back}</button>`);
        return `<section class="wizard-ai-section" aria-labelledby="wizard-ai-cloud-models-title">${renderAiSetupPanelHeading(context, 'wizard-ai-cloud-models-title', heading, i18n.t('wizard.aiSetup.models.cloud.description'))}${renderEmptyState({ icon: context.getIconSync('device-network', { width: 32, height: 32 }), title: i18n.t('wizard.aiSetup.models.cloud.empty'), actions, className: 'ui-empty-state wizard-ai-empty wizard-ai-empty--back' }).html}</section>`;
    }
    const filterLabel = context.sanitizer.attribute(i18n.t('wizard.aiSetup.models.cloud.filterPlaceholder'));
    const filter = `<div class="searchbar-container searchbar-container--collection"><input id="${AI_CLOUD_FILTER_ID}" type="search" class="form-input searchbar-input" value="${context.sanitizer.attribute(view.cloudFilter)}" placeholder="${filterLabel}" aria-label="${filterLabel}" autocomplete="off" spellcheck="false">${renderSearchFieldActions().html}</div>`;
    const rows = view.cloudModels.map((model) => renderCloudModel(context, view, model)).join('');
    return `<section class="wizard-ai-section" aria-labelledby="wizard-ai-cloud-models-title">${renderAiSetupPanelHeading(context, 'wizard-ai-cloud-models-title', heading, i18n.t('wizard.aiSetup.models.cloud.description'))}${filter}<div class="wizard-ai-scroll wizard-ai-cloud-list" role="group" aria-labelledby="wizard-ai-cloud-models-title">${rows}<p class="wizard-field-hint u-hidden" data-ai-cloud-no-match>${context.sanitizer.html(i18n.t('wizard.aiSetup.models.cloud.noMatches'))}</p></div></section>`;
};

const renderAiModelsStep = (context: WizardViewContext, view: AiSetupModelsView): string => {
    const cloud = view.showCloud ? `<div class="wizard-ai-contents" data-ai-region="cloud-models">${renderAiCloudModels(context, view)}</div>` : '';
    const local = view.showLocal ? renderLocalSection(context, view) : '';
    return `<div class="wizard-step wizard-step--ai">${renderAiSetupHeading(context, i18n.t('wizard.aiSetup.models.heading'), i18n.t('wizard.aiSetup.models.description'))}${cloud}${local}</div>`;
};

export { AI_CLOUD_FILTER_ID, AI_FIRST_CHAT_INPUT_NAME, AI_MODEL_INPUT_NAME, AI_SEARCH_FORM_ID, cloudSelectionKey, itemSelectionKey, localSelectionKey, parseSelectionKey, renderAiCloudModels, renderAiModelsStep, renderAiPickedModels };
