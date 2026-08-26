/* SoAI - Localized licensing settings value presentation [frontend/assets/ts/pages/settings/controllers/licensing/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LicensingSettingsStatus } from '@core/api/contracts/licensingSettingsContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { licensingStateNeedsAttention, licensingStateRequiresRepair } from '@core/licensing/licensingState.ts';
import { canReconcileLicensingOperation, isLicensingOperationInProgress } from '@core/licensing/operationLifecycle.ts';
import { presentDeclaration, presentEdition, presentEntitlementType, presentLicensingState } from '@core/licensing/valuePresentation.ts';
import { formatNullableEpochMsMinuteWithFallback } from '@core/primitives/dateTime.ts';
import { renderLabelAttributes, securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { renderSection, renderSelectControl, renderSettingItem, renderSettingsGroup, renderSettingsSubgroup, renderSettingsTextValue } from '@core/settings/settingsMarkup.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';

const escaped = (value: string): string => securityApi.escapeHtml(value);
const formatTimeMinute = (value: number | null): string => formatNullableEpochMsMinuteWithFallback(value, i18n.t('common.notAvailable'));
const actionButton = (action: string, label: string, variant = 'neutral', disabled = false): string => `<button type="button" class="ui-button ui-button--sm ui-variant-${variant}" data-action="${action}" ${renderLabelAttributes(label)}${disabled ? ' disabled' : ''}>${escaped(label)}</button>`;

const statusTone = (status: LicensingSettingsStatus): 'active' | 'warning' | 'danger' | 'neutral' => {
    if (licensingStateRequiresRepair(status.state)) return 'danger';
    if (licensingStateNeedsAttention(status.state)) return 'warning';
    if (status.operation && !['succeeded', 'failed', 'cancelled'].includes(status.operation.state)) return 'warning';
    return status.entitlement || status.state === 'personal_declared' ? 'active' : 'neutral';
};

const statusLabel = (status: LicensingSettingsStatus): string => {
    if (['evaluation_active', 'commercial_active', 'commercial_continuity', 'personal_os_perpetual_active', 'commercial_perpetual_active'].includes(status.state)) return i18n.t('settings.licensing.values.states.active');
    return presentLicensingState(status.state);
};

const statusValue = (status: LicensingSettingsStatus): string => {
    const tone = statusTone(status);
    return `<strong class="settings-licensing-status settings-licensing-status--${tone}">${escaped(statusLabel(status))}</strong>`;
};

const declarationEntitlement = (status: LicensingSettingsStatus): string => {
    const declaration = presentDeclaration(status.declaration);
    if (status.entitlement === null) return declaration;
    if (status.entitlement.entitlementType === 'personal_os_perpetual') return `${declaration} ${i18n.t('settings.licensing.perpetualQualifier')}`;
    return `${declaration} · ${presentEntitlementType(status.entitlement.entitlementType)}`;
};

const licensingRestartItems = (status: LicensingSettingsStatus): string[] => {
    if (!status.requiresRepairPlane || licensingStateRequiresRepair(status.state)) return [];
    return [
        renderSettingItem({
            label: i18n.t('settings.licensing.restartRequired'),
            help: i18n.t('settings.licensing.restartRequiredHelp'),
            control: actionButton('licensing-open-power', i18n.t('settings.licensing.openPowerPage'), 'warning')
        })
    ];
};

const renderDeclarationAction = (status: LicensingSettingsStatus, operationInProgress: boolean): string => {
    if (status.declaration === 'personal') {
        return renderSettingItem({ label: i18n.t('settings.licensing.declareOrganization'), help: escaped(i18n.t('licensing.base.unavailableTooltip')), className: 'full-width', control: actionButton('licensing-declare-organization', i18n.t('settings.licensing.changeLicenseType'), 'neutral', true) });
    }
    return renderSettingItem({
        label: i18n.t('settings.licensing.declarePersonal'),
        help: escaped(status.personalAttestationText),
        className: 'full-width',
        control: actionButton('licensing-declare-personal', i18n.t('settings.licensing.changeLicenseType'), 'neutral', operationInProgress)
    });
};

const capabilityLabel = (capability: string): string => {
    switch (capability) {
        case 'personal_noncommercial':
            return i18n.t('settings.licensing.values.capabilities.personalNoncommercial');
        case 'organization_evaluation':
            return i18n.t('settings.licensing.values.capabilities.organizationEvaluation');
        case 'organization_internal':
            return i18n.t('settings.licensing.values.capabilities.organizationInternal');
        case 'modification':
            return i18n.t('settings.licensing.values.capabilities.modification');
        case 'consulting_client_delivery':
            return i18n.t('settings.licensing.values.capabilities.consultingClientDelivery');
        case 'hosted_service':
            return i18n.t('settings.licensing.values.capabilities.hostedService');
        case 'managed_service':
            return i18n.t('settings.licensing.values.capabilities.managedService');
        case 'redistribution':
            return i18n.t('settings.licensing.values.capabilities.redistribution');
        case 'oem':
            return i18n.t('settings.licensing.values.capabilities.oem');
        case 'sublicensing':
            return i18n.t('settings.licensing.values.capabilities.sublicensing');
        case 'trademark_use':
            return i18n.t('settings.licensing.values.capabilities.trademarkUse');
        default:
            throw new TypeError('Licensing capability presentation is not closed.');
    }
};

const entitlementItems = (status: LicensingSettingsStatus): string[] => {
    const entitlement = status.entitlement;
    if (!entitlement) return [];
    const allowances = [entitlement.allowedPersonalDeployments === null ? null : `${i18n.t('settings.licensing.personalDeployments')}: ${String(entitlement.allowedPersonalDeployments)}`, entitlement.allowedProductionDeployments === null ? null : `${i18n.t('settings.licensing.productionDeployments')}: ${String(entitlement.allowedProductionDeployments)}`, entitlement.allowedNonProductionDeployments === null ? null : `${i18n.t('settings.licensing.nonProductionDeployments')}: ${String(entitlement.allowedNonProductionDeployments)}`].filter((value): value is string => value !== null);
    const environment = entitlement.deploymentEnvironment === null ? i18n.t('common.notAvailable') : entitlement.deploymentEnvironment === 'production' ? i18n.t('settings.licensing.production') : i18n.t('settings.licensing.nonProduction');
    const items = [renderSettingItem({ label: i18n.t('settings.licensing.environment'), help: i18n.t('settings.licensing.environmentHelp'), control: renderSettingsTextValue(environment) }), renderSettingItem({ label: i18n.t('settings.licensing.capabilities'), help: i18n.t('settings.licensing.capabilitiesHelp'), control: renderSettingsTextValue(entitlement.licensedCapabilities.map(capabilityLabel).join(', ')) }), renderSettingItem({ label: i18n.t('settings.licensing.deployments'), help: i18n.t('settings.licensing.deploymentsHelp'), control: renderSettingsTextValue(allowances.join(' · ') || i18n.t('common.notAvailable')) })];
    if (entitlement.supportHoursIncluded !== null) items.push(renderSettingItem({ label: i18n.t('settings.licensing.supportHours'), help: i18n.t('settings.licensing.supportHoursHelp'), control: renderSettingsTextValue(String(entitlement.supportHoursIncluded)) }));
    if (entitlement.perpetual) return items;
    const boundaries: Array<[string, string | null]> = [
        [i18n.t('settings.licensing.effective'), entitlement.effectiveAt],
        [i18n.t('settings.licensing.termStarts'), entitlement.termStartsAt],
        [i18n.t('settings.licensing.termEnds'), entitlement.termEndsAt],
        [i18n.t('settings.licensing.continuityStarts'), entitlement.continuityStartsAt],
        [i18n.t('settings.licensing.continuityEnds'), entitlement.continuityEndsAt]
    ];
    for (const [label, value] of boundaries) {
        if (value !== null) items.push(renderSettingItem({ label, help: '', control: renderSettingsTextValue(i18n.formatDate(new Date(value), { dateStyle: 'medium', timeStyle: 'medium' })) }));
    }
    return items;
};

const environmentControl = (id: string, selected: 'production' | 'non_production' = 'production'): string =>
    renderSelectControl({
        id,
        selected,
        compact: true,
        options: [
            { value: 'production', label: i18n.t('settings.licensing.production') },
            { value: 'non_production', label: i18n.t('settings.licensing.nonProduction') }
        ]
    });

const organizationControls = (): string =>
    `<div class="settings-licensing-organization-controls"><input id="settings-organization-legal-name" class="setting-input" autocomplete="organization" maxlength="256" placeholder="${securityApi.escapeAttribute(i18n.t('settings.licensing.organizationLegalName'))}"><input id="settings-organization-country" class="setting-input" autocomplete="country" maxlength="2" placeholder="${securityApi.escapeAttribute(i18n.t('settings.licensing.organizationCountry'))}"><input id="settings-organization-tax-id" class="setting-input" maxlength="256" placeholder="${securityApi.escapeAttribute(i18n.t('settings.licensing.organizationTaxId'))}"><input id="settings-authorized-acceptor-name" class="setting-input" autocomplete="name" maxlength="256" placeholder="${securityApi.escapeAttribute(i18n.t('settings.licensing.authorizedAcceptorName'))}"><input id="settings-authorized-acceptor-email" class="setting-input" type="email" autocomplete="email" maxlength="320" placeholder="${securityApi.escapeAttribute(i18n.t('settings.licensing.authorizedAcceptorEmail'))}"></div>`;

const entitlementTransitionItems = (status: LicensingSettingsStatus, operationInProgress: boolean): string[] => {
    const entitlement = status.entitlement;
    if (entitlement === null || !entitlement.onlineMaintenanceAvailable || operationInProgress || status.declaration !== 'organization_commercial') return [];
    const items: string[] = [];
    if (entitlement.entitlementType === 'personal_os_perpetual') {
        items.push(renderSettingItem({ label: i18n.t('settings.licensing.convertOsEvaluation'), help: i18n.t('settings.licensing.convertOsEvaluationHelp'), className: 'full-width', control: `${organizationControls()}${actionButton('licensing-convert-os-evaluation', i18n.t('settings.licensing.convertOsEvaluation'), 'warning', true)}` }));
    }
    if (entitlement.entitlementType === 'organization_evaluation' && entitlement.deploymentProduct === 'soai_os') {
        items.push(renderSettingItem({ label: i18n.t('settings.licensing.revertOsEvaluation'), help: i18n.t('settings.licensing.revertOsEvaluationHelp'), className: 'full-width', control: actionButton('licensing-revert-os-evaluation', i18n.t('settings.licensing.revertOsEvaluation'), 'warning') }));
    }
    if (entitlement.entitlementType === 'personal_os_perpetual' || entitlement.entitlementType === 'organization_evaluation') {
        const input = `<input id="settings-commercial-key" name="commercial-license-key" type="${resolveSecretInputType()}" class="setting-input setting-input--wide secret-input" autocomplete="off" spellcheck="false">`;
        items.push(renderSettingItem({ label: i18n.t('settings.licensing.convertCommercial'), help: i18n.t('settings.licensing.convertCommercialHelp'), className: 'full-width', control: `<div class="settings-licensing-key-control">${renderSecretInputControl({ inputId: 'settings-commercial-key', inputMarkup: input })}${environmentControl('settings-commercial-environment')}${actionButton('licensing-convert-commercial', i18n.t('settings.licensing.convertCommercial'), 'success', true)}</div>` }));
    }
    if (entitlement.deploymentEnvironment !== null && ['commercial_term', 'commercial_continuity', 'commercial_full_perpetual'].includes(entitlement.entitlementType)) {
        const destination = entitlement.deploymentEnvironment === 'production' ? 'non_production' : 'production';
        items.push(renderSettingItem({ label: i18n.t('settings.licensing.reclassify'), help: i18n.t('settings.licensing.reclassifyHelp'), className: 'full-width', control: `<div class="settings-licensing-action-controls">${environmentControl('settings-reclassification-environment', destination)}${actionButton('licensing-reclassify', i18n.t('settings.licensing.reclassify'), 'warning')}</div>` }));
    }
    if (entitlement.entitlementType === 'commercial_term' || entitlement.entitlementType === 'commercial_continuity') {
        items.push(renderSettingItem({ label: i18n.t('settings.licensing.retrieveTerm'), help: i18n.t('settings.licensing.retrieveTermHelp'), className: 'full-width', control: actionButton('licensing-retrieve-term', i18n.t('settings.licensing.retrieveTerm')) }));
    }
    return items;
};

const recoveryItem = (status: LicensingSettingsStatus, operationInProgress: boolean): string | null => {
    const reconcile = canReconcileLicensingOperation(status.operation) ? actionButton('licensing-reconcile', i18n.t('settings.licensing.reconcile')) : '';
    const offline = status.licenseAcceptedAtMs !== null && status.productAccessRequired && !operationInProgress ? `${actionButton('licensing-export-offline', i18n.t('settings.licensing.exportOffline'))}${actionButton('licensing-import-offline', i18n.t('settings.licensing.importOffline'))}<input id="settings-offline-certificate" class="visually-hidden" type="file" accept=".soailicense,application/vnd.soai.offline-entitlement+json,application/json,application/octet-stream">` : '';
    const deactivate =
        status.entitlement?.onlineMaintenanceAvailable === true && !operationInProgress
            ? `${renderSelectControl({
                  id: 'settings-licensing-deactivation-reason',
                  selected: 'rehost',
                  compact: true,
                  options: [
                      { value: 'rehost', label: i18n.t('settings.licensing.reasonRehost') },
                      { value: 'retired', label: i18n.t('settings.licensing.reasonRetired') },
                      { value: 'disaster_recovery', label: i18n.t('settings.licensing.reasonDisaster') },
                      { value: 'other', label: i18n.t('settings.licensing.reasonOther') }
                  ]
              })}${actionButton('licensing-deactivate', i18n.t('settings.licensing.deactivate'), 'danger')}`
            : '';
    const controls = `${reconcile}${offline}${deactivate}`;
    return controls ? renderSettingItem({ label: i18n.t('settings.licensing.recovery'), help: i18n.t('settings.licensing.reconcileHelp'), className: 'full-width', control: `<div class="settings-licensing-action-controls">${controls}</div>` }) : null;
};

const renderLicensingSettings = (status: LicensingSettingsStatus | null, soaiVersion: string | null): TrustedHtml => {
    if (status === null) return toTrustedUiHtml(renderSection({ title: i18n.t('settings.licensing.title'), description: i18n.t('settings.licensing.description'), className: 'settings-section--licensing', content: `<p class="setting-help">${escaped(i18n.t('common.loading'))}</p>` }));
    const operationInProgress = status.operation !== null && isLicensingOperationInProgress(status.operation.state);
    const summary = renderSettingsSubgroup({
        title: i18n.t('settings.licensing.summary'),
        content: renderSettingsGroup([
            renderSettingItem({ label: i18n.t('settings.licensing.status'), help: i18n.t('settings.licensing.statusHelp'), control: statusValue(status) }),
            renderSettingItem({ label: i18n.t('settings.licensing.edition'), help: escaped(status.licenseDocumentName), control: renderSettingsTextValue(`${presentEdition(status.edition)} v${soaiVersion ?? i18n.t('common.notAvailable')}`) }),
            renderSettingItem({ label: i18n.t('settings.licensing.accepted'), help: escaped(status.licenseFingerprint), className: 'settings-licensing-fingerprint', control: renderSettingsTextValue(formatTimeMinute(status.licenseAcceptedAtMs)) }),
            renderSettingItem({ label: i18n.t('settings.licensing.declarationEffective'), help: i18n.t('settings.licensing.declarationEffectiveHelp'), control: renderSettingsTextValue(formatTimeMinute(status.declarationEffectiveAtMs)) }),
            renderSettingItem({ label: i18n.t('settings.licensing.declaration'), help: i18n.t('settings.licensing.declarationHelp'), control: renderSettingsTextValue(declarationEntitlement(status)) }),
            ...entitlementItems(status),
            ...licensingRestartItems(status)
        ])
    });
    const actions: string[] = [];
    if (status.licenseAcceptedAtMs === null) actions.push(renderSettingItem({ label: i18n.t('about.licenseTitle'), help: i18n.t('licensing.errors.licenseChanged'), className: 'full-width', control: `<div class="settings-licensing-action-controls">${actionButton('licensing-review-license', i18n.t('about.licenseTitle'))}${actionButton('licensing-accept-license', i18n.t('wizard.navigation.acceptLicense'), 'success')}</div>` }));
    if (status.licenseAcceptedAtMs !== null && !operationInProgress && status.entitlement === null && status.productAccessRequired) {
        const input = `<input id="settings-license-key" name="license-key" type="${resolveSecretInputType()}" class="setting-input setting-input--wide secret-input" autocomplete="off" spellcheck="false">`;
        const environment = status.declaration === 'organization_commercial' ? environmentControl('settings-activation-environment') : '';
        actions.push(renderSettingItem({ label: i18n.t('settings.licensing.activate'), help: i18n.t('settings.licensing.activateHelp'), className: 'full-width', control: `<div class="settings-licensing-key-control">${renderSecretInputControl({ inputId: 'settings-license-key', inputMarkup: input })}${environment}${actionButton('licensing-activate', i18n.t('settings.licensing.activate'), 'success', true)}</div>` }));
    }
    actions.push(...entitlementTransitionItems(status, operationInProgress));
    const recovery = recoveryItem(status, operationInProgress);
    if (recovery !== null) actions.push(recovery);
    actions.push(renderDeclarationAction(status, operationInProgress));
    const actionSection = renderSettingsSubgroup({ title: i18n.t('settings.licensing.actions'), content: renderSettingsGroup(actions, { className: 'settings-licensing-actions' }) });
    return toTrustedUiHtml(renderSection({ title: i18n.t('settings.licensing.title'), description: i18n.t('settings.licensing.description'), className: 'settings-section--licensing', content: summary + actionSection }));
};

export { renderLicensingSettings };
