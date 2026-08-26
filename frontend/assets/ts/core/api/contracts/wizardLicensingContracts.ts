/* SoAI - Strict wizard licensing V1 response contracts [frontend/assets/ts/core/api/contracts/wizardLicensingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeLicensingCapabilities, decodeLicensingOperation, DEPLOYMENT_PRODUCTS, ENTITLEMENT_TYPES, nullableLicensingTimestamp, PRODUCT_SCOPES, requireClosedString, requireLicensingTimestamp, requireString, type DeploymentEnvironment, type DeploymentProduct, type LicensedProductScope, type LicensingCapability, type LicensingEntitlementType, type LicensingOperationState, type LicensingOperationSummary } from '@core/api/contracts/licensingEntitlementContracts.ts';
import { assertBackendEdition } from '@core/edition/backendEditionIntegrity.ts';
import { requireLicensingState, type LicensingState } from '@core/licensing/licensingState.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type WizardPayloadValue = JsonValue | undefined;

type WizardSetupState = 'uninitialized' | 'complete' | 'integrity_error';
type WizardEdition = 'soai-core' | 'soai-os';
type WizardDeclaration = 'personal' | 'organization_commercial';
type WizardResumeStep = 'license' | 'use' | 'product_access' | 'account' | 'complete';
type WizardProductAccessFlow = 'evaluation' | 'online_activation' | 'offline_activation';
type WizardOperationState = LicensingOperationState;
type WizardEntitlementType = LicensingEntitlementType;
type WizardProductScope = LicensedProductScope;
type WizardLicensingCapability = LicensingCapability;

interface WizardLegalDocumentMetadata {
    documentName: string;
    fingerprint: string;
}

interface WizardCompletedSummary {
    schemaVersion: 1;
    accountCreated: true;
    edition: WizardEdition;
    declaration: WizardDeclaration | null;
    entitlementType: WizardEntitlementType | null;
    entitlementStatus: LicensingState;
    timeBoundary: string | null;
    perpetual: boolean;
    detectedPlugins: readonly string[];
}

type WizardOperationSummary = LicensingOperationSummary;

interface WizardEntitlementSummary {
    entitlementType: WizardEntitlementType;
    licensedProductScope: WizardProductScope;
    deploymentProduct: DeploymentProduct;
    licensedCapabilities: readonly WizardLicensingCapability[];
    deploymentId: string;
    effectiveAt: string;
    termStartsAt: string | null;
    termEndsAt: string | null;
    continuityStartsAt: string | null;
    continuityEndsAt: string | null;
    deploymentEnvironment: DeploymentEnvironment | null;
}

interface WizardPendingEvaluation {
    evaluationId: string;
    pendingExpiresAtMs: number;
}

interface WizardStatusResponse {
    schemaVersion: 1;
    setupState: WizardSetupState;
    setupNeeded: boolean;
    hasUsers: boolean;
    edition: WizardEdition;
    draftRevision: number;
    licenseDocumentName: string;
    licenseFingerprint: string;
    licenseAcceptedAtMs: number | null;
    declaration: WizardDeclaration | null;
    personalAttestationRevision: string;
    personalAttestationText: string;
    personalAttestationConfirmedAtMs: number | null;
    evaluationTerms: WizardLegalDocumentMetadata | null;
    personalPurchaseTerms: WizardLegalDocumentMetadata | null;
    evaluationAcknowledgedAtMs: number | null;
    selectedProductAccessFlow: WizardProductAccessFlow | null;
    operation: WizardOperationSummary | null;
    pendingEvaluation: WizardPendingEvaluation | null;
    entitlement: WizardEntitlementSummary | null;
    resumeStep: WizardResumeStep;
    unmetPrerequisites: readonly string[];
    completedSummary: WizardCompletedSummary | null;
}

interface WizardSetupProbe {
    setupNeeded: false;
    hasUsers: boolean;
}

type WizardStatusLookupResponse = WizardStatusResponse | WizardSetupProbe;

const STATUS_FIELDS = ['schema_version', 'setup_state', 'setup_needed', 'has_users', 'edition', 'draft_revision', 'license_document_name', 'license_fingerprint', 'license_accepted_at_ms', 'declaration', 'personal_attestation_revision', 'personal_attestation_text', 'personal_attestation_confirmed_at_ms', 'evaluation_terms', 'personal_purchase_terms', 'evaluation_acknowledged_at_ms', 'selected_product_access_flow', 'operation', 'pending_evaluation', 'entitlement', 'resume_step', 'unmet_prerequisites', 'completed_summary'];

const requireEdition = (value: WizardPayloadValue, label: string): WizardEdition => {
    if (value !== 'soai-core' && value !== 'soai-os') throw new TypeError(`${label} is unsupported.`);
    return value;
};

const requireDeclaration = (value: WizardPayloadValue, label: string): WizardDeclaration => {
    if (value !== 'personal' && value !== 'organization_commercial') throw new TypeError(`${label} is unsupported.`);
    return value;
};

const requireSetupState = (value: WizardPayloadValue, label: string): WizardSetupState => {
    if (value !== 'uninitialized' && value !== 'complete' && value !== 'integrity_error') throw new TypeError(`${label} is unsupported.`);
    return value;
};

const requireResumeStep = (value: WizardPayloadValue, label: string): WizardResumeStep => {
    if (value !== 'license' && value !== 'use' && value !== 'product_access' && value !== 'account' && value !== 'complete') throw new TypeError(`${label} is unsupported.`);
    return value;
};

const requireBoolean = (value: WizardPayloadValue, label: string): boolean => {
    if (typeof value !== 'boolean') throw new TypeError(`${label} must be boolean.`);
    return value;
};

const requireInteger = (value: WizardPayloadValue, label: string): number => readRequiredNonNegativeIntegerValue(value, label);

const nullableInteger = (value: WizardPayloadValue, label: string): number | null => (value === null ? null : requireInteger(value, label));

const PRODUCT_ACCESS_FLOWS: ReadonlySet<WizardProductAccessFlow> = new Set(['evaluation', 'online_activation', 'offline_activation']);

const requireFingerprint = (value: WizardPayloadValue, label: string): string => {
    const fingerprint = requireString(value, label);
    if (!/^sha256:[a-f0-9]{64}$/.test(fingerprint)) throw new TypeError(`${label} must be a SHA-256 fingerprint.`);
    return fingerprint;
};

const decodeLegalDocumentMetadata = (value: WizardPayloadValue, label: string): WizardLegalDocumentMetadata | null => {
    if (value === null) return null;
    const record = requireRecord(value, label);
    assertExactRecordKeys(record, ['document_name', 'fingerprint'], label);
    return {
        documentName: requireString(record['document_name'], `${label}.document_name`),
        fingerprint: requireFingerprint(record['fingerprint'], `${label}.fingerprint`)
    };
};

const decodeOperation = (value: WizardPayloadValue): WizardOperationSummary | null => decodeLicensingOperation(value, 'Wizard status operation');

const decodeStringArray = (value: WizardPayloadValue, label: string): string[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    const entries = value.map((entry, index) => requireString(entry, `${label}[${String(index)}]`));
    if (new Set(entries).size !== entries.length) throw new TypeError(`${label} cannot contain duplicates.`);
    return entries;
};

const decodeEntitlement = (value: WizardPayloadValue): WizardEntitlementSummary | null => {
    if (value === null) return null;
    const record = requireRecord(value, 'Wizard status entitlement');
    assertExactRecordKeys(record, ['entitlement_type', 'licensed_product_scope', 'deployment_product', 'licensed_capabilities', 'deployment_id', 'effective_at', 'term_starts_at', 'term_ends_at', 'continuity_starts_at', 'continuity_ends_at', 'deployment_environment'], 'Wizard status entitlement');
    const deploymentEnvironment = record['deployment_environment'];
    if (deploymentEnvironment !== null && deploymentEnvironment !== 'production' && deploymentEnvironment !== 'non_production') throw new TypeError('Wizard status entitlement deployment environment is invalid.');
    const entitlementType = requireClosedString(record['entitlement_type'], ENTITLEMENT_TYPES, 'Wizard status entitlement type');
    const termStartsAt = nullableLicensingTimestamp(record['term_starts_at'], 'Wizard status entitlement.term_starts_at');
    const termEndsAt = nullableLicensingTimestamp(record['term_ends_at'], 'Wizard status entitlement.term_ends_at');
    const continuityStartsAt = nullableLicensingTimestamp(record['continuity_starts_at'], 'Wizard status entitlement.continuity_starts_at');
    const continuityEndsAt = nullableLicensingTimestamp(record['continuity_ends_at'], 'Wizard status entitlement.continuity_ends_at');
    const hasTerm = termStartsAt !== null && termEndsAt !== null;
    const hasContinuity = continuityStartsAt !== null && continuityEndsAt !== null;
    if ((termStartsAt === null) !== (termEndsAt === null) || (continuityStartsAt === null) !== (continuityEndsAt === null)) throw new TypeError('Wizard status entitlement boundary pair is incomplete.');
    if ((entitlementType === 'organization_evaluation' || entitlementType === 'commercial_term') !== hasTerm || (entitlementType === 'commercial_continuity') !== hasContinuity) throw new TypeError('Wizard status entitlement boundaries are contradictory.');
    const licensedCapabilities = decodeLicensingCapabilities(record['licensed_capabilities'], 'Wizard status entitlement.licensed_capabilities', entitlementType === 'organization_evaluation' || entitlementType === 'commercial_continuity');
    if ((entitlementType === 'organization_evaluation' || entitlementType === 'commercial_continuity') !== (licensedCapabilities.length === 0)) throw new TypeError('Wizard status entitlement capabilities are contradictory.');
    const licensedProductScope = requireClosedString(record['licensed_product_scope'], PRODUCT_SCOPES, 'Wizard status entitlement product scope');
    const deploymentProduct = requireClosedString(record['deployment_product'], DEPLOYMENT_PRODUCTS, 'Wizard status entitlement deployment product');
    const isCommercial = entitlementType === 'commercial_term' || entitlementType === 'commercial_continuity' || entitlementType === 'commercial_full_perpetual';
    if ((licensedProductScope === 'soai_core' && deploymentProduct !== 'soai_core') || (licensedProductScope === 'soai_os' && deploymentProduct !== 'soai_os')) throw new TypeError('Wizard status entitlement product binding is contradictory.');
    if (isCommercial !== (deploymentEnvironment !== null) || (entitlementType === 'personal_os_perpetual' && (licensedProductScope !== 'soai_os' || deploymentProduct !== 'soai_os'))) throw new TypeError('Wizard status entitlement environment is contradictory.');
    return {
        entitlementType,
        licensedProductScope,
        deploymentProduct,
        licensedCapabilities,
        deploymentId: requireString(record['deployment_id'], 'Wizard status entitlement.deployment_id'),
        effectiveAt: requireLicensingTimestamp(record['effective_at'], 'Wizard status entitlement.effective_at'),
        termStartsAt,
        termEndsAt,
        continuityStartsAt,
        continuityEndsAt,
        deploymentEnvironment
    };
};

const decodePendingEvaluation = (value: WizardPayloadValue): WizardPendingEvaluation | null => {
    if (value === null) return null;
    const record = requireRecord(value, 'Wizard pending evaluation');
    assertExactRecordKeys(record, ['evaluation_id', 'pending_expires_at_ms'], 'Wizard pending evaluation');
    return { evaluationId: requireString(record['evaluation_id'], 'Wizard pending evaluation.evaluation_id'), pendingExpiresAtMs: requireInteger(record['pending_expires_at_ms'], 'Wizard pending evaluation.pending_expires_at_ms') };
};

const decodeWizardCompletedSummary = (value: WizardPayloadValue): WizardStatusResponse['completedSummary'] => {
    if (value === null) return null;
    const record = requireRecord(value, 'Wizard completed summary');
    assertExactRecordKeys(record, ['schema_version', 'account_created', 'edition', 'declaration', 'entitlement_type', 'entitlement_status', 'time_boundary', 'perpetual', 'detected_plugins'], 'Wizard completed summary');
    if (record['schema_version'] !== 1 || record['account_created'] !== true || typeof record['perpetual'] !== 'boolean') throw new TypeError('Wizard completed summary has invalid fixed fields.');
    const entitlementType = record['entitlement_type'] === null ? null : requireClosedString(record['entitlement_type'], ENTITLEMENT_TYPES, 'Wizard completed summary.entitlement_type');
    const timeBoundary = nullableLicensingTimestamp(record['time_boundary'], 'Wizard completed summary.time_boundary');
    const perpetual = record['perpetual'];
    const isPerpetualType = entitlementType === 'personal_os_perpetual' || entitlementType === 'commercial_full_perpetual';
    if (perpetual !== isPerpetualType || (entitlementType === 'organization_evaluation' || entitlementType === 'commercial_term') !== (timeBoundary !== null)) throw new TypeError('Wizard completed summary entitlement boundary is contradictory.');
    return {
        schemaVersion: 1,
        accountCreated: true,
        edition: requireEdition(record['edition'], 'Wizard completed summary.edition'),
        declaration: record['declaration'] === null ? null : requireDeclaration(record['declaration'], 'Wizard completed summary.declaration'),
        entitlementType,
        entitlementStatus: requireLicensingState(record['entitlement_status'], 'Wizard completed summary.entitlement_status'),
        timeBoundary,
        perpetual,
        detectedPlugins: decodeStringArray(record['detected_plugins'], 'Wizard completed summary.detected_plugins')
    };
};

const decodeWizardStatusResponse = (value: ApiResponsePayload): WizardStatusResponse => {
    const record = requireRecord(value, 'Wizard status response');
    assertExactRecordKeys(record, STATUS_FIELDS, 'Wizard status response');
    if (record['schema_version'] !== 1) throw new TypeError('Wizard status response.schema_version must be 1.');
    const setupState = requireSetupState(record['setup_state'], 'Wizard status response.setup_state');
    const setupNeeded = requireBoolean(record['setup_needed'], 'Wizard status response.setup_needed');
    const hasUsers = requireBoolean(record['has_users'], 'Wizard status response.has_users');
    const completedSummary = decodeWizardCompletedSummary(record['completed_summary']);
    if (setupNeeded !== (setupState === 'uninitialized')) throw new TypeError('Wizard status setup fields are contradictory.');
    if (setupState === 'uninitialized' && hasUsers) throw new TypeError('Wizard status user presence is contradictory.');
    if (setupState === 'complete' && !hasUsers) throw new TypeError('Wizard status user presence is contradictory.');
    if ((setupState === 'complete') !== (completedSummary !== null)) throw new TypeError('Wizard status completion summary is contradictory.');
    const edition = requireEdition(record['edition'], 'Wizard status response.edition');
    assertBackendEdition(edition);
    const evaluationTerms = decodeLegalDocumentMetadata(record['evaluation_terms'], 'Wizard status evaluation terms');
    const personalPurchaseTerms = decodeLegalDocumentMetadata(record['personal_purchase_terms'], 'Wizard status personal purchase terms');
    if ((edition === 'soai-core') !== (evaluationTerms !== null) || (edition === 'soai-os') !== (personalPurchaseTerms !== null)) throw new TypeError('Wizard status edition legal documents are contradictory.');
    if (completedSummary !== null && (completedSummary.edition !== edition || completedSummary.declaration !== (record['declaration'] === null ? null : requireDeclaration(record['declaration'], 'Wizard status response.declaration')))) throw new TypeError('Wizard status completed summary does not match current state.');
    return {
        schemaVersion: 1,
        setupState,
        setupNeeded,
        hasUsers,
        edition,
        draftRevision: requireInteger(record['draft_revision'], 'Wizard status response.draft_revision'),
        licenseDocumentName: requireString(record['license_document_name'], 'Wizard status response.license_document_name'),
        licenseFingerprint: requireFingerprint(record['license_fingerprint'], 'Wizard status response.license_fingerprint'),
        licenseAcceptedAtMs: nullableInteger(record['license_accepted_at_ms'], 'Wizard status response.license_accepted_at_ms'),
        declaration: record['declaration'] === null ? null : requireDeclaration(record['declaration'], 'Wizard status response.declaration'),
        personalAttestationRevision: requireString(record['personal_attestation_revision'], 'Wizard status response.personal_attestation_revision'),
        personalAttestationText: requireString(record['personal_attestation_text'], 'Wizard status response.personal_attestation_text'),
        personalAttestationConfirmedAtMs: nullableInteger(record['personal_attestation_confirmed_at_ms'], 'Wizard status response.personal_attestation_confirmed_at_ms'),
        evaluationTerms,
        personalPurchaseTerms,
        evaluationAcknowledgedAtMs: nullableInteger(record['evaluation_acknowledged_at_ms'], 'Wizard status response.evaluation_acknowledged_at_ms'),
        selectedProductAccessFlow: record['selected_product_access_flow'] === null ? null : requireClosedString(record['selected_product_access_flow'], PRODUCT_ACCESS_FLOWS, 'Wizard status product access flow'),
        operation: decodeOperation(record['operation']),
        pendingEvaluation: decodePendingEvaluation(record['pending_evaluation']),
        entitlement: decodeEntitlement(record['entitlement']),
        resumeStep: requireResumeStep(record['resume_step'], 'Wizard status response.resume_step'),
        unmetPrerequisites: decodeStringArray(record['unmet_prerequisites'], 'Wizard status response.unmet_prerequisites'),
        completedSummary
    };
};

const decodeWizardStatusLookupResponse = (value: ApiResponsePayload): WizardStatusLookupResponse => {
    const record = requireRecord(value, 'Wizard status lookup response');
    if ('schema_version' in record) return decodeWizardStatusResponse(record);
    assertExactRecordKeys(record, ['setup_needed', 'has_users'], 'Wizard setup probe');
    if (requireBoolean(record['setup_needed'], 'Wizard setup probe.setup_needed')) throw new TypeError('A setup-required response must include the detailed wizard status.');
    return { setupNeeded: false, hasUsers: requireBoolean(record['has_users'], 'Wizard setup probe.has_users') };
};

const isDetailedWizardStatus = (value: WizardStatusLookupResponse): value is WizardStatusResponse => 'schemaVersion' in value;

export { decodeEntitlement, decodeOperation, decodeWizardCompletedSummary, decodeWizardStatusLookupResponse, decodeWizardStatusResponse, decodeStringArray, isDetailedWizardStatus };
export type { WizardCompletedSummary, WizardDeclaration, WizardEdition, WizardEntitlementSummary, WizardLicensingCapability, WizardOperationState, WizardOperationSummary, WizardProductScope, WizardResumeStep, WizardSetupState, WizardStatusLookupResponse, WizardStatusResponse };
