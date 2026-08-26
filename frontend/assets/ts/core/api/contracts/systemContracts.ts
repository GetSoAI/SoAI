/* SoAI - Frontend system API boundary contracts [frontend/assets/ts/core/api/contracts/systemContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { assertExactRecordKeys, readRequiredJsonObjectArrayValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readNullableFiniteIntegerValue, readRequiredFiniteIntegerValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface SystemHealthResponse {
    status: 'ok' | 'degraded';
    edition: 'soai-core' | 'soai-os';
    powerOperations: 'healthy' | 'degraded';
    product: 'soai';
    version: string;
    instanceId: string;
    instanceName: string | null;
    scheme: 'http' | 'https';
    port: number;
    preferredPort: number;
    fallbackActive: boolean;
}
interface InstanceNameResponse {
    instanceName: string | null;
}
interface SystemInfoResponse {
    licenseName: string;
    description: string;
    soaiVersion: string | null;
    platform: string | null;
    pythonVersion: string | null;
}
interface SystemLicenseResponse {
    schemaVersion: 1;
    edition: 'soai-core' | 'soai-os';
    documentName: string;
    fingerprint: string;
    licenseText: string;
}
interface SecurityHardeningFinding {
    issueId: string;
    message: string;
    configKeys: string[];
    workspaceReferences: string[];
}
interface SecurityHardeningAudit {
    secure: boolean;
    issueCount: number;
    findings: SecurityHardeningFinding[];
    configKeys: string[];
    workspaceReferences: string[];
}
interface SystemStateDefinition {
    name: string;
    color: string;
    description: string;
    group: string;
    tags: string[];
}
interface SystemStateDefinitionsResponse {
    default: string;
    states: Record<string, SystemStateDefinition>;
    allowedColors: string[];
    tags: Record<string, string[]>;
}
type SystemStatusResponse = {
    timestampMs: number;
    soaiVersion: string;
    mainState: string | null;
    pluginStates: JsonObject;
    pluginStateVersion: number;
    hardware: JsonObject;
    orchestrator: JsonObject;
    systemState: JsonObject;
};
interface MessageResponse {
    message: string;
}
interface CancellationRegistryResetResponse extends MessageResponse {
    previousActiveTokens: number;
    previousCancelledCancellationCount: number;
}
interface CancellationRegistrySweepResponse {
    removedTokens: number;
    cancellationsCleared: number;
    remainingCancellations: number;
}
interface TaskCancellationResponse {
    success: true;
    taskId: string;
    cancellationRequested: true;
    cancellationRequestedAtMs: number | null;
    status: string;
}
interface CircuitBreakerSnapshot {
    pluginName: string;
    state: 'closed' | 'open' | 'half-open';
    failureCount: number;
    failureThreshold: number;
    lastFailureAtMs: number;
    isOpen: boolean;
    recoveryTimeoutSec: number;
    failureWindowSec: number;
}
interface SystemLogSnapshot {
    entries: JsonObject[];
    source: string;
    limit: number;
}
interface SystemLogSourcesResponse {
    sources: string[];
}

const decodeMessage = (value: ApiResponsePayload, label: string): MessageResponse => {
    const record = requireRecord(value, label);
    return { message: readRequiredStringValue(record['message'], `${label}.message`) };
};

const decodeSystemHealth = (value: ApiResponsePayload): SystemHealthResponse => {
    const record = requireRecord(value, 'System health response');
    assertExactRecordKeys(record, ['status', 'edition', 'power_operations', 'product', 'version', 'instance_id', 'instance_name', 'scheme', 'port', 'preferred_port', 'fallback_active'], 'System health response');
    const port = readRequiredFiniteIntegerValue(record['port'], 'System health response.port');
    const preferredPort = readRequiredFiniteIntegerValue(record['preferred_port'], 'System health response.preferred_port');
    const fallbackActive = readRequiredBooleanValue(record['fallback_active'], 'System health response.fallback_active');
    if (port < 1 || port > 65535 || preferredPort < 1 || preferredPort > 65535) throw new TypeError('System health response ports must be from 1 through 65535');
    if (fallbackActive !== (port !== preferredPort)) throw new TypeError('System health response fallback state is inconsistent');
    return {
        status: readRequiredEnumValue(record['status'], 'System health response.status', ['ok', 'degraded']),
        edition: readRequiredEnumValue(record['edition'], 'System health response.edition', ['soai-core', 'soai-os']),
        powerOperations: readRequiredEnumValue(record['power_operations'], 'System health response.power_operations', ['healthy', 'degraded']),
        product: readRequiredEnumValue(record['product'], 'System health response.product', ['soai']),
        version: readRequiredTrimmedStringValue(record['version'], 'System health response.version'),
        instanceId: readRequiredTrimmedStringValue(record['instance_id'], 'System health response.instance_id'),
        instanceName: readNullableTrimmedStringValue(record['instance_name'], 'System health response.instance_name'),
        scheme: readRequiredEnumValue(record['scheme'], 'System health response.scheme', ['http', 'https']),
        port,
        preferredPort,
        fallbackActive
    };
};

const decodeInstanceNameResponse = (value: ApiResponsePayload): InstanceNameResponse => {
    const record = requireRecord(value, 'Instance name response');
    return { instanceName: readNullableTrimmedStringValue(record['instance_name'], 'Instance name response.instance_name') };
};

const serializeInstanceNameUpdateRequest = (instanceName: string | null): JsonObject => ({ 'instance_name': instanceName });

const decodeSystemInfo = (value: ApiResponsePayload): SystemInfoResponse => {
    const record = requireRecord(value, 'System info response');
    return { licenseName: readRequiredTrimmedStringValue(record['license_name'], 'System info response.license_name'), description: readRequiredStringValue(record['description'], 'System info response.description'), soaiVersion: readNullableTrimmedStringValue(record['soai_version'], 'System info response.soai_version'), platform: readNullableTrimmedStringValue(record['platform'], 'System info response.platform'), pythonVersion: readNullableTrimmedStringValue(record['python_version'], 'System info response.python_version') };
};

const decodeSystemLicense = (value: ApiResponsePayload): SystemLicenseResponse => {
    const record = requireRecord(value, 'System license response');
    const schemaVersion = readRequiredFiniteIntegerValue(record['schema_version'], 'System license response.schema_version');
    if (schemaVersion !== 1) throw new TypeError('System license response.schema_version must be 1');
    return { schemaVersion: 1, edition: readRequiredEnumValue(record['edition'], 'System license response.edition', ['soai-core', 'soai-os']), documentName: readRequiredTrimmedStringValue(record['document_name'], 'System license response.document_name'), fingerprint: readRequiredTrimmedStringValue(record['fingerprint'], 'System license response.fingerprint'), licenseText: readRequiredStringValue(record['license_text'], 'System license response.license_text') };
};

const decodeRequirementsText = (value: ApiResponsePayload): string => readRequiredStringValue(value, 'System requirements response');

const decodeSecurityFinding = (value: JsonValue, index: number): SecurityHardeningFinding => {
    const label = `Security hardening finding[${String(index)}]`;
    const record = requireRecord(value, label);
    return { issueId: readRequiredTrimmedStringValue(record['issue_id'], `${label}.issue_id`), message: readRequiredStringValue(record['message'], `${label}.message`), configKeys: readRequiredStringArrayValue(record['config_keys'], `${label}.config_keys`), workspaceReferences: readRequiredStringArrayValue(record['workspace_references'], `${label}.workspace_references`) };
};

const decodeSecurityHardeningAudit = (value: ApiResponsePayload): SecurityHardeningAudit => {
    const record = requireRecord(value, 'Security hardening audit');
    const findings = readRequiredJsonObjectArrayValue(record['findings'], 'Security hardening audit.findings').map(decodeSecurityFinding);
    const issueCount = readRequiredNonNegativeIntegerValue(record['issue_count'], 'Security hardening audit.issue_count');
    if (issueCount !== findings.length) throw new TypeError('Security hardening audit.issue_count does not match findings');
    return { secure: readRequiredBooleanValue(record['secure'], 'Security hardening audit.secure'), issueCount: issueCount, findings, configKeys: readRequiredStringArrayValue(record['config_keys'], 'Security hardening audit.config_keys'), workspaceReferences: readRequiredStringArrayValue(record['workspace_references'], 'Security hardening audit.workspace_references') };
};

const decodeStringArrayRecord = (value: JsonValue | undefined, label: string): Record<string, string[]> => {
    const record = requireRecord(value, label);
    const result: Record<string, string[]> = {};
    for (const [key, entry] of Object.entries(record)) result[key] = readRequiredStringArrayValue(entry, `${label}.${key}`);
    return result;
};

const decodeStateDefinitionRecord = (value: JsonValue | undefined): Record<string, SystemStateDefinition> => {
    const record = requireRecord(value, 'System state definitions.states');
    const result: Record<string, SystemStateDefinition> = {};
    for (const [key, entry] of Object.entries(record)) {
        const definition = requireRecord(entry, `System state definitions.states.${key}`);
        result[key] = { name: readRequiredTrimmedStringValue(definition['name'], `System state definitions.states.${key}.name`), color: readRequiredTrimmedStringValue(definition['color'], `System state definitions.states.${key}.color`), description: readRequiredStringValue(definition['description'], `System state definitions.states.${key}.description`), group: readRequiredTrimmedStringValue(definition['group'], `System state definitions.states.${key}.group`), tags: readRequiredStringArrayValue(definition['tags'], `System state definitions.states.${key}.tags`) };
    }
    return result;
};

const decodeSystemStateDefinitions = (value: ApiResponsePayload): SystemStateDefinitionsResponse => {
    const record = requireRecord(value, 'System state definitions');
    return { default: readRequiredTrimmedStringValue(record['default'], 'System state definitions.default'), states: decodeStateDefinitionRecord(record['states']), allowedColors: readRequiredStringArrayValue(record['allowed_colors'], 'System state definitions.allowed_colors'), tags: decodeStringArrayRecord(record['tags'], 'System state definitions.tags') };
};

const decodeSystemStatus = (value: ApiResponsePayload): SystemStatusResponse => {
    const record = requireRecord(value, 'System status response');
    return { timestampMs: readRequiredFiniteIntegerValue(record['timestamp_ms'], 'System status response.timestamp_ms'), soaiVersion: readRequiredTrimmedStringValue(record['soai_version'], 'System status response.soai_version'), mainState: readNullableTrimmedStringValue(record['main_state'], 'System status response.main_state'), pluginStates: requireRecord(record['plugin_states'], 'System status response.plugin_states'), pluginStateVersion: readRequiredNonNegativeIntegerValue(record['plugin_state_version'], 'System status response.plugin_state_version'), hardware: requireRecord(record['hardware'], 'System status response.hardware'), orchestrator: requireRecord(record['orchestrator'], 'System status response.orchestrator'), systemState: requireRecord(record['system_state'], 'System status response.system_state') };
};

const decodeJsonObject = (value: ApiResponsePayload, label: string): JsonObject => requireRecord(value, label);
const decodeResetMessage = (value: ApiResponsePayload, label: string): MessageResponse => decodeMessage(value, label);

const decodeCancellationRegistryReset = (value: ApiResponsePayload): CancellationRegistryResetResponse => {
    const record = requireRecord(value, 'Cancellation registry reset response');
    return { message: readRequiredStringValue(record['message'], 'Cancellation registry reset response.message'), previousActiveTokens: readRequiredNonNegativeIntegerValue(record['previous_active_tokens'], 'Cancellation registry reset response.previous_active_tokens'), previousCancelledCancellationCount: readRequiredNonNegativeIntegerValue(record['previous_cancelled_cancellation_count'], 'Cancellation registry reset response.previous_cancelled_cancellation_count') };
};

const decodeCancellationRegistrySweep = (value: ApiResponsePayload): CancellationRegistrySweepResponse => {
    const record = requireRecord(value, 'Cancellation registry sweep response');
    return { removedTokens: readRequiredNonNegativeIntegerValue(record['removed_tokens'], 'Cancellation registry sweep response.removed_tokens'), cancellationsCleared: readRequiredNonNegativeIntegerValue(record['cancellations_cleared'], 'Cancellation registry sweep response.cancellations_cleared'), remainingCancellations: readRequiredNonNegativeIntegerValue(record['remaining_cancellations'], 'Cancellation registry sweep response.remaining_cancellations') };
};

const decodeTaskCancellation = (value: ApiResponsePayload): TaskCancellationResponse => {
    const record = requireRecord(value, 'Task cancellation response');
    const success = readRequiredBooleanValue(record['success'], 'Task cancellation response.success');
    const cancellationRequested = readRequiredBooleanValue(record['cancellation_requested'], 'Task cancellation response.cancellation_requested');
    if (!success || !cancellationRequested) throw new TypeError('Task cancellation response must confirm cancellation');
    return { success: true, taskId: readRequiredTrimmedStringValue(record['task_id'], 'Task cancellation response.task_id'), cancellationRequested: true, cancellationRequestedAtMs: readNullableFiniteIntegerValue(record['cancellation_requested_at_ms'], 'Task cancellation response.cancellation_requested_at_ms'), status: readRequiredTrimmedStringValue(record['status'], 'Task cancellation response.status') };
};

const decodeCircuitBreakerSnapshot = (value: ApiResponsePayload): CircuitBreakerSnapshot => {
    const record = requireRecord(value, 'Circuit breaker snapshot');
    return { pluginName: readRequiredTrimmedStringValue(record['plugin_name'], 'Circuit breaker snapshot.plugin_name'), state: readRequiredEnumValue(record['state'], 'Circuit breaker snapshot.state', ['closed', 'open', 'half-open']), failureCount: readRequiredNonNegativeIntegerValue(record['failure_count'], 'Circuit breaker snapshot.failure_count'), failureThreshold: readRequiredNonNegativeIntegerValue(record['failure_threshold'], 'Circuit breaker snapshot.failure_threshold'), lastFailureAtMs: readRequiredNonNegativeIntegerValue(record['last_failure_at_ms'], 'Circuit breaker snapshot.last_failure_at_ms'), isOpen: readRequiredBooleanValue(record['is_open'], 'Circuit breaker snapshot.is_open'), recoveryTimeoutSec: readRequiredNonNegativeIntegerValue(record['recovery_timeout_sec'], 'Circuit breaker snapshot.recovery_timeout_sec'), failureWindowSec: readRequiredNonNegativeIntegerValue(record['failure_window_sec'], 'Circuit breaker snapshot.failure_window_sec') };
};

const decodeSystemLogSnapshot = (value: ApiResponsePayload): SystemLogSnapshot => {
    const record = requireRecord(value, 'System log snapshot');
    return { entries: readRequiredJsonObjectArrayValue(record['entries'], 'System log snapshot.entries'), source: readRequiredTrimmedStringValue(record['source'], 'System log snapshot.source'), limit: readRequiredNonNegativeIntegerValue(record['limit'], 'System log snapshot.limit') };
};

const decodeSystemLogSources = (value: ApiResponsePayload): SystemLogSourcesResponse => {
    const record = requireRecord(value, 'System log sources response');
    return { sources: readRequiredStringArrayValue(record['sources'], 'System log sources response.sources') };
};

const decodeRawResponse = (value: ApiResponsePayload, label: string): Response => {
    if (!(value instanceof Response)) throw new TypeError(`${label} must be a Response`);
    return value;
};

export { decodeCancellationRegistryReset, decodeCancellationRegistrySweep, decodeCircuitBreakerSnapshot, decodeInstanceNameResponse, decodeJsonObject, decodeRawResponse, decodeRequirementsText, decodeResetMessage, decodeSecurityHardeningAudit, decodeSystemHealth, decodeSystemInfo, decodeSystemLicense, decodeSystemLogSnapshot, decodeSystemLogSources, decodeSystemStateDefinitions, decodeSystemStatus, decodeTaskCancellation, serializeInstanceNameUpdateRequest };
export type { CancellationRegistryResetResponse, CancellationRegistrySweepResponse, CircuitBreakerSnapshot, InstanceNameResponse, MessageResponse, SecurityHardeningAudit, SecurityHardeningFinding, SystemHealthResponse, SystemInfoResponse, SystemLicenseResponse, SystemLogSnapshot, SystemLogSourcesResponse, SystemStateDefinition, SystemStateDefinitionsResponse, SystemStatusResponse, TaskCancellationResponse };
