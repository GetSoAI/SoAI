/* SoAI - Authenticated final V1 licensing status contracts [frontend/assets/ts/core/api/contracts/licensingSettingsContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeLicensingCapabilities, decodeLicensingOperation, DEPLOYMENT_PRODUCTS, ENTITLEMENT_TYPES, PRODUCT_SCOPES, requireClosedString, requireLicensingTimestamp, type DeploymentEnvironment, type DeploymentProduct, type LicensedProductScope, type LicensingCapability, type LicensingEntitlementType, type LicensingOperationSummary, type LicensingValidationMode } from '@core/api/contracts/licensingEntitlementContracts.ts';
import type { WizardDeclaration, WizardEdition } from '@core/api/contracts/wizardLicensingContracts.ts';
import { requireLicensingState, type LicensingState } from '@core/licensing/licensingState.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type LicensingPayloadValue = JsonValue | undefined;

interface LicensingAdministrativeEntitlement {
    entitlementType: LicensingEntitlementType;
    licensedProductScope: LicensedProductScope;
    deploymentProduct: DeploymentProduct;
    validationMode: LicensingValidationMode;
    licensedCapabilities: readonly LicensingCapability[];
    deploymentId: string;
    entitlementGeneration: number;
    deploymentEnvironment: DeploymentEnvironment | null;
    allowedPersonalDeployments: number | null;
    allowedProductionDeployments: number | null;
    allowedNonProductionDeployments: number | null;
    supportHoursIncluded: number | null;
    effectiveAt: string;
    termStartsAt: string | null;
    termEndsAt: string | null;
    continuityStartsAt: string | null;
    continuityEndsAt: string | null;
    perpetual: boolean;
    onlineMaintenanceAvailable: boolean;
}

interface LicensingSettingsStatus {
    schemaVersion: 1;
    edition: WizardEdition;
    state: LicensingState;
    requiresRepairPlane: boolean;
    draftRevision: number;
    declaration: WizardDeclaration | null;
    productAccessRequired: boolean;
    declarationEffectiveAtMs: number | null;
    personalAttestationRevision: string;
    personalAttestationText: string;
    personalAttestationConfirmedAtMs: number | null;
    licenseDocumentName: string;
    licenseFingerprint: string;
    licenseAcceptedAtMs: number | null;
    operation: LicensingOperationSummary | null;
    entitlement: LicensingAdministrativeEntitlement | null;
}

const stringValue = (value: LicensingPayloadValue, label: string): string => {
    if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be a non-empty string.`);
    return value;
};

const integerValue = (value: LicensingPayloadValue, label: string): number => readRequiredNonNegativeIntegerValue(value, label);
const nullableInteger = (value: LicensingPayloadValue, label: string): number | null => (value === null ? null : integerValue(value, label));
const nullableTimestamp = (value: LicensingPayloadValue, label: string): string | null => (value === null ? null : requireLicensingTimestamp(value, label));

const validationMode = (value: LicensingPayloadValue): LicensingValidationMode => {
    if (value !== 'term_fixed' && value !== 'local_only') throw new TypeError('Licensing validation mode is invalid.');
    return value;
};

const deploymentEnvironment = (value: LicensingPayloadValue): DeploymentEnvironment | null => {
    if (value !== null && value !== 'production' && value !== 'non_production') throw new TypeError('Licensing deployment environment is invalid.');
    return value;
};

const decodeAdministrativeEntitlement = (value: LicensingPayloadValue): LicensingAdministrativeEntitlement | null => {
    if (value === null) return null;
    const label = 'Licensing administrative entitlement';
    const record = requireRecord(value, label);
    assertExactRecordKeys(record, ['entitlement_type', 'licensed_product_scope', 'deployment_product', 'validation_mode', 'licensed_capabilities', 'deployment_id', 'entitlement_generation', 'deployment_environment', 'allowed_personal_deployments', 'allowed_production_deployments', 'allowed_non_production_deployments', 'support_hours_included', 'effective_at', 'term_starts_at', 'term_ends_at', 'continuity_starts_at', 'continuity_ends_at', 'perpetual', 'online_maintenance_available'], label);
    if (typeof record['perpetual'] !== 'boolean' || typeof record['online_maintenance_available'] !== 'boolean') throw new TypeError('Licensing entitlement flags are invalid.');
    const entitlementType = requireClosedString(record['entitlement_type'], ENTITLEMENT_TYPES, 'Licensing entitlement type');
    const resolvedValidationMode = validationMode(record['validation_mode']);
    const expectedPerpetual = entitlementType === 'personal_os_perpetual' || entitlementType === 'commercial_full_perpetual';
    const termStartsAt = nullableTimestamp(record['term_starts_at'], 'Licensing term start');
    const termEndsAt = nullableTimestamp(record['term_ends_at'], 'Licensing term end');
    const continuityStartsAt = nullableTimestamp(record['continuity_starts_at'], 'Licensing continuity start');
    const continuityEndsAt = nullableTimestamp(record['continuity_ends_at'], 'Licensing continuity end');
    const hasTerm = termStartsAt !== null && termEndsAt !== null;
    const hasContinuity = continuityStartsAt !== null && continuityEndsAt !== null;
    const expectedMode = entitlementType === 'organization_evaluation' || expectedPerpetual ? 'local_only' : 'term_fixed';
    if (record['perpetual'] !== expectedPerpetual || resolvedValidationMode !== expectedMode) throw new TypeError('Licensing entitlement duration is contradictory.');
    if ((entitlementType === 'organization_evaluation' || entitlementType === 'commercial_term') !== hasTerm || (entitlementType === 'commercial_continuity') !== hasContinuity) throw new TypeError('Licensing entitlement boundaries are contradictory.');
    if ((termStartsAt === null) !== (termEndsAt === null) || (continuityStartsAt === null) !== (continuityEndsAt === null)) throw new TypeError('Licensing entitlement boundary pair is incomplete.');
    const licensedCapabilities = decodeLicensingCapabilities(record['licensed_capabilities'], 'Licensing licensed capabilities', entitlementType === 'organization_evaluation' || entitlementType === 'commercial_continuity');
    if ((entitlementType === 'organization_evaluation' || entitlementType === 'commercial_continuity') !== (licensedCapabilities.length === 0)) throw new TypeError('Licensing entitlement capabilities are contradictory.');
    const licensedProductScope = requireClosedString(record['licensed_product_scope'], PRODUCT_SCOPES, 'Licensing product scope');
    const deploymentProduct = requireClosedString(record['deployment_product'], DEPLOYMENT_PRODUCTS, 'Licensing deployment product');
    const resolvedEnvironment = deploymentEnvironment(record['deployment_environment']);
    const allowedPersonalDeployments = nullableInteger(record['allowed_personal_deployments'], 'Licensing personal deployment allowance');
    const allowedProductionDeployments = nullableInteger(record['allowed_production_deployments'], 'Licensing production deployment allowance');
    const allowedNonProductionDeployments = nullableInteger(record['allowed_non_production_deployments'], 'Licensing non-production deployment allowance');
    const supportHoursIncluded = nullableInteger(record['support_hours_included'], 'Licensing support-hour allowance');
    if ((licensedProductScope === 'soai_core' && deploymentProduct !== 'soai_core') || (licensedProductScope === 'soai_os' && deploymentProduct !== 'soai_os')) throw new TypeError('Licensing entitlement product binding is contradictory.');
    const personal = entitlementType === 'personal_os_perpetual';
    const evaluation = entitlementType === 'organization_evaluation';
    const commercial = !personal && !evaluation;
    if (personal && (licensedProductScope !== 'soai_os' || deploymentProduct !== 'soai_os' || resolvedEnvironment !== null || allowedPersonalDeployments !== 3 || allowedProductionDeployments !== null || allowedNonProductionDeployments !== null || supportHoursIncluded !== null)) throw new TypeError('Personal licensing entitlement is contradictory.');
    if (evaluation && (resolvedEnvironment !== null || allowedPersonalDeployments !== null || allowedProductionDeployments !== null || allowedNonProductionDeployments !== null || supportHoursIncluded !== null)) throw new TypeError('Evaluation licensing entitlement is contradictory.');
    if (commercial && (resolvedEnvironment === null || allowedPersonalDeployments !== null || allowedProductionDeployments === null || allowedNonProductionDeployments === null)) throw new TypeError('Commercial licensing entitlement is contradictory.');
    if ((entitlementType === 'commercial_term' || entitlementType === 'commercial_continuity') && (allowedProductionDeployments !== 3 || allowedNonProductionDeployments !== 3)) throw new TypeError('Standard commercial deployment allowances are contradictory.');
    if (entitlementType === 'commercial_full_perpetual' && ((allowedProductionDeployments ?? 0) < 1 || (allowedNonProductionDeployments ?? 0) < 1)) throw new TypeError('Commercial perpetual deployment allowances are contradictory.');
    if (entitlementType === 'commercial_term' ? ![1, 2, 4].includes(supportHoursIncluded ?? -1) : commercial && supportHoursIncluded !== null) throw new TypeError('Commercial support entitlement is contradictory.');
    const entitlementGeneration = integerValue(record['entitlement_generation'], 'Licensing entitlement generation');
    if (entitlementGeneration < 1) throw new TypeError('Licensing entitlement generation is invalid.');
    return {
        entitlementType,
        licensedProductScope,
        deploymentProduct,
        validationMode: resolvedValidationMode,
        licensedCapabilities,
        deploymentId: stringValue(record['deployment_id'], 'Licensing deployment identity'),
        entitlementGeneration,
        deploymentEnvironment: resolvedEnvironment,
        allowedPersonalDeployments,
        allowedProductionDeployments,
        allowedNonProductionDeployments,
        supportHoursIncluded,
        effectiveAt: requireLicensingTimestamp(record['effective_at'], 'Licensing entitlement effective time'),
        termStartsAt,
        termEndsAt,
        continuityStartsAt,
        continuityEndsAt,
        perpetual: record['perpetual'],
        onlineMaintenanceAvailable: record['online_maintenance_available']
    };
};

const decodeLicensingSettingsStatus = (value: ApiResponsePayload): LicensingSettingsStatus => {
    const record = requireRecord(value, 'Licensing settings status');
    assertExactRecordKeys(record, ['schema_version', 'edition', 'state', 'requires_repair_plane', 'draft_revision', 'declaration', 'product_access_required', 'declaration_effective_at_ms', 'personal_attestation_revision', 'personal_attestation_text', 'personal_attestation_confirmed_at_ms', 'license_document_name', 'license_fingerprint', 'license_accepted_at_ms', 'operation', 'entitlement'], 'Licensing settings status');
    if (record['schema_version'] !== 1) throw new TypeError('Licensing settings status schema must be V1.');
    if (record['edition'] !== 'soai-core' && record['edition'] !== 'soai-os') throw new TypeError('Licensing settings edition is invalid.');
    if (typeof record['requires_repair_plane'] !== 'boolean') throw new TypeError('Licensing repair-plane value is invalid.');
    if (typeof record['product_access_required'] !== 'boolean') throw new TypeError('Licensing product-access requirement is invalid.');
    const declaration = record['declaration'];
    if (declaration !== null && declaration !== 'personal' && declaration !== 'organization_commercial') throw new TypeError('Licensing declaration is invalid.');
    const fingerprint = stringValue(record['license_fingerprint'], 'Licensing fingerprint');
    if (!/^sha256:[a-f0-9]{64}$/.test(fingerprint)) throw new TypeError('Licensing fingerprint is invalid.');
    return {
        schemaVersion: 1,
        edition: record['edition'],
        state: requireLicensingState(record['state']),
        requiresRepairPlane: record['requires_repair_plane'],
        draftRevision: integerValue(record['draft_revision'], 'Licensing draft revision'),
        declaration,
        productAccessRequired: record['product_access_required'],
        declarationEffectiveAtMs: nullableInteger(record['declaration_effective_at_ms'], 'Licensing declaration effective time'),
        personalAttestationRevision: stringValue(record['personal_attestation_revision'], 'Licensing personal attestation revision'),
        personalAttestationText: stringValue(record['personal_attestation_text'], 'Licensing personal attestation text'),
        personalAttestationConfirmedAtMs: nullableInteger(record['personal_attestation_confirmed_at_ms'], 'Licensing personal attestation confirmation time'),
        licenseDocumentName: stringValue(record['license_document_name'], 'Licensing document name'),
        licenseFingerprint: fingerprint,
        licenseAcceptedAtMs: nullableInteger(record['license_accepted_at_ms'], 'Licensing acceptance time'),
        operation: decodeLicensingOperation(record['operation'], 'Licensing operation'),
        entitlement: decodeAdministrativeEntitlement(record['entitlement'])
    };
};

export { decodeLicensingSettingsStatus };
export type { LicensingAdministrativeEntitlement, LicensingSettingsStatus, LicensingState };
