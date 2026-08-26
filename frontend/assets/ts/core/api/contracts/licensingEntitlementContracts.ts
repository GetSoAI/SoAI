/* SoAI - Shared final V1 licensing operation and entitlement contracts [frontend/assets/ts/core/api/contracts/licensingEntitlementContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { assertExactRecordKeys, requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type LicensingPayloadValue = JsonValue | undefined;
type LicensingOperationType = 'evaluation' | 'os-evaluation-conversion' | 'os-evaluation-reversion' | 'activation' | 'commercial-conversion' | 'deployment-reclassification' | 'term-renewal' | 'operation-reconciliation' | 'deactivation' | 'offline_export' | 'offline_import';
type LicensingOperationState = 'prepared' | 'sending' | 'outcome_unknown' | 'reconciling' | 'retry_wait' | 'succeeded' | 'failed' | 'cancelled';
type LicensingEntitlementType = 'organization_evaluation' | 'commercial_term' | 'commercial_continuity' | 'personal_os_perpetual' | 'commercial_full_perpetual';
type LicensedProductScope = 'soai_core' | 'soai_os' | 'soai_core_and_os';
type DeploymentProduct = 'soai_core' | 'soai_os';
type DeploymentEnvironment = 'production' | 'non_production';
type LicensingValidationMode = 'term_fixed' | 'local_only';
type LicensingCapability = 'personal_noncommercial' | 'organization_evaluation' | 'organization_internal' | 'modification' | 'consulting_client_delivery' | 'hosted_service' | 'managed_service' | 'redistribution' | 'oem' | 'sublicensing' | 'trademark_use';

interface LicensingOperationSummary {
    operationType: LicensingOperationType;
    state: LicensingOperationState;
    attemptCount: number;
    lastAttemptAtMs: number | null;
    nextRetryAtMs: number | null;
    terminalCode: string | null;
    updatedAtMs: number;
}

const OPERATION_TYPES: ReadonlySet<LicensingOperationType> = new Set(['evaluation', 'os-evaluation-conversion', 'os-evaluation-reversion', 'activation', 'commercial-conversion', 'deployment-reclassification', 'term-renewal', 'operation-reconciliation', 'deactivation', 'offline_export', 'offline_import']);
const OPERATION_STATES: ReadonlySet<LicensingOperationState> = new Set(['prepared', 'sending', 'outcome_unknown', 'reconciling', 'retry_wait', 'succeeded', 'failed', 'cancelled']);
const TERMINAL_CODES = new Set(['activation_not_found', 'operation_not_found', 'idempotency_conflict', 'invalid_input', 'authority_rejected', 'invalid_credential', 'personal_capacity_reached', 'production_capacity_reached', 'non_production_capacity_reached', 'licensed_product_scope_mismatch', 'license_not_effective', 'license_expired', 'license_suspended', 'license_terminated', 'evaluation_ineligible', 'provider_outcome_unknown', 'renewal_not_reconciled', 'invalid_signature', 'invalid_binding', 'invalid_contract']);
const ENTITLEMENT_TYPES: ReadonlySet<LicensingEntitlementType> = new Set(['organization_evaluation', 'commercial_term', 'commercial_continuity', 'personal_os_perpetual', 'commercial_full_perpetual']);
const PRODUCT_SCOPES: ReadonlySet<LicensedProductScope> = new Set(['soai_core', 'soai_os', 'soai_core_and_os']);
const DEPLOYMENT_PRODUCTS: ReadonlySet<DeploymentProduct> = new Set(['soai_core', 'soai_os']);
const CAPABILITIES: ReadonlySet<LicensingCapability> = new Set(['personal_noncommercial', 'organization_evaluation', 'organization_internal', 'modification', 'consulting_client_delivery', 'hosted_service', 'managed_service', 'redistribution', 'oem', 'sublicensing', 'trademark_use']);

const requireString = (value: LicensingPayloadValue, label: string): string => {
    if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be a non-empty string.`);
    return value;
};

const requireClosedString = <Allowed extends string>(value: LicensingPayloadValue, allowed: ReadonlySet<Allowed>, label: string): Allowed => {
    const resolved = requireString(value, label);
    for (const candidate of allowed) if (candidate === resolved) return candidate;
    throw new TypeError(`${label} is unsupported.`);
};

const requireLicensingTimestamp = (value: LicensingPayloadValue, label: string): string => {
    const timestamp = requireString(value, label);
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(timestamp)) throw new TypeError(`${label} must be an exact UTC timestamp.`);
    const date = new Date(timestamp);
    if (!Number.isFinite(date.getTime()) || date.toISOString().replace('.000Z', 'Z') !== timestamp) throw new TypeError(`${label} must be an exact UTC timestamp.`);
    return timestamp;
};

const nullableLicensingTimestamp = (value: LicensingPayloadValue, label: string): string | null => (value === null ? null : requireLicensingTimestamp(value, label));
const nullableInteger = (value: LicensingPayloadValue, label: string): number | null => (value === null ? null : readRequiredNonNegativeIntegerValue(value, label));

const decodeLicensingCapabilities = (value: LicensingPayloadValue, label: string, allowEmpty = false): LicensingCapability[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
    const capabilities = value.map((entry, index) => requireClosedString(entry, CAPABILITIES, `${label}[${String(index)}]`));
    if ((!allowEmpty && !capabilities.length) || new Set(capabilities).size !== capabilities.length) throw new TypeError(`${label} is unsupported.`);
    if (capabilities.join('\0') !== [...capabilities].sort((left, right) => left.localeCompare(right, 'en')).join('\0')) throw new TypeError(`${label} must be sorted.`);
    return capabilities;
};

const decodeLicensingOperation = (value: LicensingPayloadValue, label: string): LicensingOperationSummary | null => {
    if (value === null) return null;
    const record = requireRecord(value, label);
    assertExactRecordKeys(record, ['operation_type', 'state', 'attempt_count', 'last_attempt_at_ms', 'next_retry_at_ms', 'terminal_code', 'updated_at_ms'], label);
    const state = requireClosedString(record['state'], OPERATION_STATES, `${label}.state`);
    const terminalCode = record['terminal_code'] === null ? null : requireString(record['terminal_code'], `${label}.terminal_code`);
    const nextRetryAtMs = nullableInteger(record['next_retry_at_ms'], `${label}.next_retry_at_ms`);
    if (terminalCode !== null && !TERMINAL_CODES.has(terminalCode)) throw new TypeError(`${label} terminal code is unsupported.`);
    if ((state === 'retry_wait' || state === 'outcome_unknown') !== (nextRetryAtMs !== null)) throw new TypeError(`${label} retry state is contradictory.`);
    if ((state === 'failed') !== (terminalCode !== null)) throw new TypeError(`${label} terminal state is contradictory.`);
    return {
        operationType: requireClosedString(record['operation_type'], OPERATION_TYPES, `${label}.operation_type`),
        state,
        attemptCount: readRequiredNonNegativeIntegerValue(record['attempt_count'], `${label}.attempt_count`),
        lastAttemptAtMs: nullableInteger(record['last_attempt_at_ms'], `${label}.last_attempt_at_ms`),
        nextRetryAtMs,
        terminalCode,
        updatedAtMs: readRequiredNonNegativeIntegerValue(record['updated_at_ms'], `${label}.updated_at_ms`)
    };
};

export { decodeLicensingCapabilities, decodeLicensingOperation, nullableLicensingTimestamp, requireClosedString, requireLicensingTimestamp, requireString, CAPABILITIES, DEPLOYMENT_PRODUCTS, ENTITLEMENT_TYPES, PRODUCT_SCOPES };
export type { DeploymentEnvironment, DeploymentProduct, LicensedProductScope, LicensingCapability, LicensingEntitlementType, LicensingOperationState, LicensingOperationSummary, LicensingOperationType, LicensingValidationMode };
