/* SoAI - Wizard product access staged decision view [frontend/assets/ts/pages/wizard/rendering/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LicensingLegalDocument, LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import { requireLicensingEditionContribution, type LicensingEditionContribution } from '@core/edition/licensingContribution.ts';
import { i18n } from '@core/i18n/index.ts';
import { canReconcileLicensingOperation, isLicensingOperationInProgress } from '@core/licensing/operationLifecycle.ts';
import { presentLicensingOperationState } from '@core/licensing/operationPresentation.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderRequiredFieldLabelHtml } from '@core/ui/forms/requiredMarker.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import type { ProductAccessFlow, WizardViewContext } from '@pages/wizard/types.ts';

const ISO_COUNTRY_CODES_URL = 'https://www.iso.org/obp/ui/#search/code/';

const documentTitle = (documentId: string): string => {
    switch (documentId) {
        case 'soai_core_license':
            return i18n.t('wizard.productAccess.documents.soaiCoreLicense');
        case 'standard_commercial_license':
            return i18n.t('wizard.productAccess.documents.standardCommercialLicense');
        case 'organization_evaluation_terms':
            return i18n.t('wizard.productAccess.documents.organizationEvaluationTerms');
        case 'soai_os_license':
            return i18n.t('wizard.productAccess.documents.soaiOsLicense');
        case 'personal_os_purchase_terms':
            return i18n.t('wizard.productAccess.documents.personalOsPurchaseTerms');
        default:
            throw new TypeError(`Wizard product access document title is unavailable for ${documentId}`);
    }
};

const uniqueDocuments = (documents: readonly LicensingLegalDocument[]): readonly LicensingLegalDocument[] => {
    const identities = new Set<string>();
    return documents.filter((document) => {
        if (identities.has(document.documentId)) return false;
        identities.add(document.documentId);
        return true;
    });
};

const renderDocument = (context: WizardViewContext, flow: LicensingLegalFlow, document: LicensingLegalDocument): string => {
    const title = documentTitle(document.documentId);
    const readLabel = i18n.t('wizard.productAccess.documents.readAction');
    const interactiveLabel = context.sanitizer.attribute(`${readLabel}: ${title}`);
    return `<details id="wizard-document-${flow}-${context.sanitizer.attribute(document.documentId)}" class="wizard-legal-document"><summary><span><strong>${context.sanitizer.html(title)}</strong><small>${context.sanitizer.html(i18n.t('wizard.productAccess.documents.version', { version: document.version }))}</small></span><span class="wizard-document-read">${context.sanitizer.html(readLabel)}</span></summary><p class="wizard-document-fingerprint"><span>${i18n.t('wizard.license.fingerprint')}</span><code>${context.sanitizer.html(document.fingerprint)}</code></p><pre class="wizard-legal-document-text" tabindex="0" aria-label="${interactiveLabel}" data-tooltip="${interactiveLabel}">${context.sanitizer.html(document.licenseText)}</pre></details>`;
};

const renderGoverningDocuments = (context: WizardViewContext, flow: LicensingLegalFlow): string => {
    const documentSet = context.state.legalDocumentSets.get(flow);
    if (documentSet === undefined || documentSet.documents.length === 0) throw new TypeError(`Wizard product access requires governing documents for ${flow}`);
    const rows = uniqueDocuments(documentSet.documents)
        .map((document) => renderDocument(context, flow, document))
        .join('');
    return `<section class="wizard-governing-documents" aria-labelledby="wizard-${flow}-documents-title"><div class="wizard-panel-heading"><h4 id="wizard-${flow}-documents-title">${i18n.t('wizard.productAccess.documents.heading')}</h4><p>${i18n.t('wizard.productAccess.documents.description')}</p></div>${rows}</section>`;
};

const field = (id: string, name: string, label: string, placeholder: string, attributes = ''): string => `<div class="wizard-form-group"><label for="${id}">${renderRequiredFieldLabelHtml(label)}</label><input id="${id}" name="${name}" class="wizard-form-input form-input" placeholder="${placeholder}" required${attributes}></div>`;

const renderOrganizationForm = (context: WizardViewContext): string =>
    `<form id="wizard-organization-form" class="wizard-product-access-form" novalidate>${field('wizard-organization-country', 'country-code', i18n.t('wizard.productAccess.organization.countryCode'), i18n.t('wizard.productAccess.organization.countryCodePlaceholder'), ' minlength="2" maxlength="2" pattern="[A-Za-z]{2}" aria-describedby="wizard-country-hint"')}<small id="wizard-country-hint" class="wizard-field-hint">${i18n.t('wizard.productAccess.organization.countryCodeHint')} <a class="external-link-confirmation" href="${ISO_COUNTRY_CODES_URL}" data-href="${ISO_COUNTRY_CODES_URL}" target="_blank" rel="noopener noreferrer">${i18n.t('wizard.productAccess.organization.countryCodeDirectory')}</a></small>${field('wizard-organization-name', 'legal-name', i18n.t('wizard.productAccess.organization.legalName'), i18n.t('wizard.productAccess.organization.legalNamePlaceholder'), ' autocomplete="organization" maxlength="256"')}${field('wizard-organization-tax', 'registration-or-tax-id', i18n.t('wizard.productAccess.organization.registrationOrTaxId'), i18n.t('wizard.productAccess.organization.registrationOrTaxIdPlaceholder'), ' maxlength="256"')}${field('wizard-acceptor-name', 'authorized-acceptor-name', i18n.t('wizard.productAccess.organization.acceptorName'), i18n.t('wizard.productAccess.organization.acceptorNamePlaceholder'), ' autocomplete="name" maxlength="256"')}${field('wizard-acceptor-email', 'authorized-acceptor-email', i18n.t('wizard.productAccess.organization.acceptorEmail'), i18n.t('wizard.productAccess.organization.acceptorEmailPlaceholder'), ' type="email" autocomplete="email" maxlength="320"')}${renderGoverningDocuments(context, 'core_evaluation')}<label class="wizard-attestation"><input id="wizard-evaluation-acknowledgement" name="authority-attested" type="checkbox" required${context.state.evaluationAcknowledged ? ' checked' : ''}><span>${i18n.t('wizard.productAccess.evaluation.acknowledge')}</span></label></form>`;

const renderDeploymentEnvironment = (inputId: string): string => {
    const select = `<select id="${inputId}" class="form-input"><option value="production">${i18n.t('wizard.productAccess.environment.production')}</option><option value="non_production">${i18n.t('wizard.productAccess.environment.nonProduction')}</option></select>`;
    return `<div class="wizard-form-group"><label for="${inputId}">${i18n.t('wizard.productAccess.environment.label')}</label>${renderStandardDropdownSelectControl(select)}</div>`;
};

const renderPersonalOffer = (context: WizardViewContext, contribution: LicensingEditionContribution): string => {
    const offer = contribution.getPersonalOffer();
    const terms = context.state.personalPurchaseTerms;
    if (offer === null) return '';
    if (terms === null) throw new TypeError('Wizard personal offer requires purchase terms');
    const details = offer.details.map((detail) => `<li>${context.sanitizer.html(detail)}</li>`).join('');
    return `<section class="wizard-personal-offer"><span class="wizard-access-badge">${context.sanitizer.html(offer.badge)}</span><div class="wizard-price"><strong>${context.sanitizer.html(offer.price)}</strong><span>${context.sanitizer.html(offer.cadence)}</span></div><h4>${context.sanitizer.html(offer.title)}</h4><p>${context.sanitizer.html(offer.description)}</p><ul>${details}</ul><a href="#wizard-document-personal_os_activation-personal_os_purchase_terms">${context.sanitizer.html(offer.termsLabel)}</a><a class="ui-button ui-variant-accent external-link-confirmation" href="${context.sanitizer.attribute(contribution.purchaseUrl)}" data-href="${context.sanitizer.attribute(contribution.purchaseUrl)}" target="_blank" rel="noopener noreferrer">${context.sanitizer.html(contribution.getPurchaseLabel())}</a></section>`;
};

const renderChoice = (flow: ProductAccessFlow, selected: ProductAccessFlow | null): string => {
    const title = flow === 'evaluation' ? i18n.t('wizard.productAccess.evaluation.title') : flow === 'online_activation' ? i18n.t('wizard.productAccess.key.title') : i18n.t('wizard.productAccess.offline.title');
    const description = flow === 'evaluation' ? i18n.t('wizard.productAccess.evaluation.description') : flow === 'online_activation' ? i18n.t('wizard.productAccess.key.description') : i18n.t('wizard.productAccess.offline.description');
    const needs = flow === 'evaluation' ? i18n.t('wizard.productAccess.evaluation.needs') : flow === 'online_activation' ? i18n.t('wizard.productAccess.key.needs') : i18n.t('wizard.productAccess.offline.needs');
    return `<label class="wizard-choice-card${selected === flow ? ' is-selected' : ''}"><input type="radio" name="wizard-product-access" value="${flow}"${selected === flow ? ' checked' : ''}><span class="wizard-choice-orb"></span><span><strong>${title}</strong><small>${description}</small><em>${needs}</em></span></label>`;
};

const renderContact = (context: WizardViewContext, contribution: LicensingEditionContribution): string => `<aside class="wizard-commercial-help"><a class="wizard-contact-link external-link-confirmation" href="${context.sanitizer.attribute(contribution.contactUrl)}" data-href="${context.sanitizer.attribute(contribution.contactUrl)}" target="_blank" rel="noopener noreferrer">${context.sanitizer.html(contribution.getContactLabel())}</a></aside>`;

const renderEvaluationPanel = (context: WizardViewContext, contribution: LicensingEditionContribution, selected: ProductAccessFlow | null): string => {
    const status = context.state.status;
    const pending = status?.pendingEvaluation ?? null;
    const body = pending === null ? renderOrganizationForm(context) : renderGoverningDocuments(context, 'core_evaluation');
    const title = pending === null ? i18n.t('wizard.productAccess.evaluation.title') : i18n.t('wizard.productAccess.evaluation.pendingTitle');
    const description = pending === null ? i18n.t('wizard.productAccess.evaluation.description') : i18n.t('wizard.productAccess.evaluation.pendingDescription');
    return `<section class="wizard-access-panel${selected === 'evaluation' ? '' : ' u-hidden'}" data-product-access-panel="evaluation" aria-labelledby="wizard-evaluation-title" tabindex="-1"><div class="wizard-panel-heading"><h3 id="wizard-evaluation-title">${title}</h3><p>${description}</p></div>${body}${renderContact(context, contribution)}<div class="wizard-action-feedback"><p id="wizard-evaluation-action-reason" class="wizard-action-reason" data-wizard-action-reason role="status"></p><div class="wizard-error${context.state.inlineError ? '' : ' u-hidden'}" role="alert" data-wizard-licensing-error>${context.sanitizer.html(context.state.inlineError ?? '')}</div></div></section>`;
};

const renderOnlinePanel = (context: WizardViewContext, contribution: LicensingEditionContribution, selected: ProductAccessFlow | null): string => {
    const personal = context.state.status?.edition === 'soai-os' && context.state.status.declaration === 'personal';
    const flow: LicensingLegalFlow = personal ? 'personal_os_activation' : 'commercial_activation';
    const keyInput = `<input id="wizard-product-key" name="license-key" type="${resolveSecretInputType()}" class="form-input secret-input" autocomplete="off" spellcheck="false" maxlength="192" placeholder="${i18n.t('wizard.productAccess.key.placeholder')}" aria-describedby="wizard-key-hint">`;
    return `<section class="wizard-access-panel${selected === 'online_activation' ? '' : ' u-hidden'}" data-product-access-panel="online_activation" aria-labelledby="wizard-key-title" tabindex="-1"><div class="wizard-panel-heading"><h3 id="wizard-key-title">${i18n.t('wizard.productAccess.key.title')}</h3><p>${i18n.t('wizard.productAccess.key.description')}</p></div>${personal ? renderPersonalOffer(context, contribution) : renderDeploymentEnvironment('wizard-online-deployment-environment')}<div class="wizard-form-group"><label for="wizard-product-key">${renderRequiredFieldLabelHtml(i18n.t('wizard.productAccess.key.title'))}</label>${renderSecretInputControl({ inputId: 'wizard-product-key', inputMarkup: keyInput })}<small id="wizard-key-hint" class="wizard-field-hint">${i18n.t('wizard.productAccess.key.description')}</small></div>${renderGoverningDocuments(context, flow)}<label class="wizard-attestation"><input id="wizard-activation-acceptance" type="checkbox"><span>${i18n.t('wizard.productAccess.key.acceptance')}</span></label>${renderContact(context, contribution)}<div class="wizard-action-feedback"><p id="wizard-online_activation-action-reason" class="wizard-action-reason" data-wizard-action-reason role="status"></p><div class="wizard-error${context.state.inlineError ? '' : ' u-hidden'}" role="alert" data-wizard-licensing-error>${context.sanitizer.html(context.state.inlineError ?? '')}</div></div></section>`;
};

const renderOfflinePanel = (context: WizardViewContext, contribution: LicensingEditionContribution, selected: ProductAccessFlow | null): string => {
    const reconcileLabel = i18n.t('wizard.productAccess.reconcile');
    const importLabel = i18n.t('wizard.productAccess.offline.import');
    const reconcileAttribute = context.sanitizer.attribute(reconcileLabel);
    const importAttribute = context.sanitizer.attribute(importLabel);
    const reconcile = canReconcileLicensingOperation(context.state.status?.operation ?? null) ? `<button type="button" class="ui-button ui-variant-neutral" data-action="wizard-reconcile" data-licensing-mutation aria-label="${reconcileAttribute}" data-tooltip="${reconcileAttribute}">${context.sanitizer.html(reconcileLabel)}</button>` : '';
    return `<section class="wizard-access-panel${selected === 'offline_activation' ? '' : ' u-hidden'}" data-product-access-panel="offline_activation" aria-labelledby="wizard-offline-title" tabindex="-1"><div class="wizard-panel-heading"><h3 id="wizard-offline-title">${i18n.t('wizard.productAccess.offline.title')}</h3><p>${i18n.t('wizard.productAccess.offline.description')}</p></div>${context.state.status?.declaration === 'organization_commercial' ? renderDeploymentEnvironment('wizard-offline-deployment-environment') : ''}<div class="wizard-offline-actions"><button type="button" class="ui-button ui-variant-neutral" data-action="wizard-import-offline" data-licensing-mutation aria-label="${importAttribute}" data-tooltip="${importAttribute}">${context.sanitizer.html(importLabel)}</button><input id="wizard-offline-certificate" class="visually-hidden" type="file" accept=".soailicense,application/vnd.soai.offline-entitlement+json,application/json,application/octet-stream">${reconcile}</div>${renderContact(context, contribution)}<div class="wizard-action-feedback"><p id="wizard-offline_activation-action-reason" class="wizard-action-reason" data-wizard-action-reason role="status"></p><div class="wizard-error${context.state.inlineError ? '' : ' u-hidden'}" role="alert" data-wizard-licensing-error>${context.sanitizer.html(context.state.inlineError ?? '')}</div></div></section>`;
};

const renderProductAccessView = (context: WizardViewContext): string => {
    const status = context.state.status;
    if (status === null || status.declaration === null || (status.edition === 'soai-core' && status.declaration === 'personal')) throw new TypeError('Wizard product access status is not renderable');
    if (status.edition === 'soai-os' && status.selectedProductAccessFlow === 'evaluation') throw new TypeError('Wizard product access flow is unavailable for SoAI OS');
    const contribution = requireLicensingEditionContribution();
    const selected = status.selectedProductAccessFlow;
    const evaluationChoice = status.edition === 'soai-core' ? renderChoice('evaluation', selected) : '';
    const operationText = status.operation === null ? '' : presentLicensingOperationState(status.operation.state);
    const operationInProgress = status.operation !== null && isLicensingOperationInProgress(status.operation.state);
    return `<div class="wizard-step wizard-step--product-access"><div class="wizard-section-heading"><span class="wizard-eyebrow">${i18n.t('wizard.productAccess.eyebrow')}</span><h2>${i18n.t('wizard.productAccess.heading')}</h2><p>${i18n.t('wizard.productAccess.guidance')}</p></div><div class="wizard-operation-banner${status.operation === null ? ' u-hidden' : ''}" role="status"><span data-wizard-operation-status>${context.sanitizer.html(operationText)}</span><small data-wizard-operation-warning${operationInProgress ? '' : ' class="u-hidden"'}>${i18n.t('wizard.productAccess.operation.switchWarning')}</small></div><div class="wizard-choice-grid wizard-choice-grid--access" role="radiogroup" aria-label="${context.sanitizer.attribute(i18n.t('wizard.productAccess.heading'))}">${evaluationChoice}${renderChoice('online_activation', selected)}${renderChoice('offline_activation', selected)}</div>${status.edition === 'soai-core' ? renderEvaluationPanel(context, contribution, selected) : ''}${renderOnlinePanel(context, contribution, selected)}${renderOfflinePanel(context, contribution, selected)}<p id="wizard-path-prompt" class="wizard-path-prompt${selected === null ? '' : ' u-hidden'}" data-wizard-path-prompt>${i18n.t('wizard.productAccess.blocked.choosePath')}</p></div>`;
};

export { renderProductAccessView };
