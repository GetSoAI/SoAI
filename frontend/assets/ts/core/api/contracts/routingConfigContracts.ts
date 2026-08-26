/* SoAI - Shared API routing configuration contracts [frontend/assets/ts/core/api/contracts/routingConfigContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { decodeVirtualModelResponse, type VirtualModelResponse } from '@core/api/contracts/virtualModelContracts.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface RoutingFailover {
    primary: string;
    secondary: string;
}

interface RoutingHealthChecks {
    INTERVAL_SEC: number;
    JITTER_FRACTION: number;
    STREAMING_IDLE_TIMEOUT_SEC: number;
    NON_STREAMING_TIMEOUT_SEC: number;
    STREAMING_PREFILL_MIN_TOKENS_PER_SEC: number;
    STREAMING_PREFILL_OVERHEAD_SEC: number;
    PING_TIMEOUT_SEC: number;
    STUCK_STATE_TIMEOUT_SEC: number;
    PENDING_STARTUP_TASK_TIMEOUT_SEC: number;
    RECOVERY_TIMEOUT_SEC: number;
    FAILURE_WINDOW_SEC: number;
    MAX_RECOVERY_ATTEMPTS: number;
    PLANNER_WORKER_COUNT: number;
    FAIR_DISPATCH_ENABLED: boolean;
    FAIR_DISPATCH_MAX_PER_PLUGIN: number;
    VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC: number;
    MAX_CONCURRENT_TASKS_PER_PLUGIN: {
        DEFAULT: number;
        PER_PLUGIN: Record<string, number>;
    };
    COMMAND_TIMEOUTS_SEC: {
        PLUGIN_STOP: number;
        PLUGIN_LOAD_MODEL: number;
    };
}

interface RoutingConfigResponse {
    maxConcurrentPlugins: number;
    taskQueueMaxSize: number;
    schedulerSafetyNetDelaySec: number;
    durableQueueLeaseTtlSec: number;
    durableQueueRecoverySweepSec: number;
    durableQueueHardLimitTasks: number;
    minFreeDiskBytesForAccept: number;
    pluginPrefetchWindowDefault: number;
    standardPriorityAgingSec: number;
    flexPriorityAgingSec: number;
    cancelOnClientDisconnect: boolean;
    httpAsyncAcceptDefault: boolean;
    acceptanceDbBusyTimeoutSec: number;
    inferenceTaskRetentionDays: number;
    ownerRunningLimitsDefault: number;
    ownerRunningLimitsByOwnerType: Record<string, number>;
    deduplicationEnabled: boolean;
    deduplicationKeys: string[];
    promptQueuing: boolean;
    queuePromptSlotLimit: number;
    fairTaskRotation: boolean;
    virtualModels: VirtualModelResponse[];
    failovers: RoutingFailover[];
    healthChecks: RoutingHealthChecks;
}

interface RoutingConfigSnapshot {
    virtualModels: VirtualModelResponse[];
    failovers: RoutingFailover[];
    routingConfig: RoutingConfigResponse;
}

const readNonNegativeNumber = (value: JsonValue | undefined, label: string): number => {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) {
        throw new TypeError(`${label} must be a non-negative finite number.`);
    }
    return value;
};

const readNonNegativeIntegerRecord = (value: JsonValue | undefined, label: string): Record<string, number> => {
    const record = requireRecord(value, label);
    const result: Record<string, number> = {};
    for (const [key, entry] of Object.entries(record)) {
        result[key] = readRequiredNonNegativeIntegerValue(entry, `${label}.${key}`);
    }
    return result;
};

const readStringArray = (value: JsonValue | undefined, label: string): string[] => {
    if (!Array.isArray(value)) {
        throw new TypeError(`${label} must be an array.`);
    }
    return value.map((entry, index) => {
        if (!isString(entry)) {
            throw new TypeError(`${label}[${String(index)}] must be a string.`);
        }
        return entry;
    });
};

const decodeFailovers = (value: JsonValue | undefined, label: string): RoutingFailover[] => {
    if (!Array.isArray(value)) {
        throw new TypeError(`${label} must be an array.`);
    }
    return value.map((entry, index) => {
        const entryLabel = `${label}[${String(index)}]`;
        const record = requireRecord(entry, entryLabel);
        return {
            primary: readRequiredTrimmedString(record, 'primary', `${entryLabel}.primary`),
            secondary: readRequiredTrimmedString(record, 'secondary', `${entryLabel}.secondary`)
        };
    });
};

const decodeVirtualModels = (value: JsonValue | undefined, label: string): VirtualModelResponse[] => {
    if (!Array.isArray(value)) {
        throw new TypeError(`${label} must be an array.`);
    }
    return value.map((entry, index) => decodeVirtualModelResponse(entry, `${label}[${String(index)}]`));
};

const decodeRoutingHealthChecks = (value: JsonValue | undefined): RoutingHealthChecks => {
    const label = 'Routing config response.health_checks';
    const record = requireRecord(value, label);
    const taskLimits = requireRecord(record['MAX_CONCURRENT_TASKS_PER_PLUGIN'], `${label}.MAX_CONCURRENT_TASKS_PER_PLUGIN`);
    const timeouts = requireRecord(record['COMMAND_TIMEOUTS_SEC'], `${label}.COMMAND_TIMEOUTS_SEC`);
    return {
        INTERVAL_SEC: readNonNegativeNumber(record['INTERVAL_SEC'], `${label}.INTERVAL_SEC`),
        JITTER_FRACTION: readNonNegativeNumber(record['JITTER_FRACTION'], `${label}.JITTER_FRACTION`),
        STREAMING_IDLE_TIMEOUT_SEC: readNonNegativeNumber(record['STREAMING_IDLE_TIMEOUT_SEC'], `${label}.STREAMING_IDLE_TIMEOUT_SEC`),
        NON_STREAMING_TIMEOUT_SEC: readNonNegativeNumber(record['NON_STREAMING_TIMEOUT_SEC'], `${label}.NON_STREAMING_TIMEOUT_SEC`),
        STREAMING_PREFILL_MIN_TOKENS_PER_SEC: readNonNegativeNumber(record['STREAMING_PREFILL_MIN_TOKENS_PER_SEC'], `${label}.STREAMING_PREFILL_MIN_TOKENS_PER_SEC`),
        STREAMING_PREFILL_OVERHEAD_SEC: readNonNegativeNumber(record['STREAMING_PREFILL_OVERHEAD_SEC'], `${label}.STREAMING_PREFILL_OVERHEAD_SEC`),
        PING_TIMEOUT_SEC: readNonNegativeNumber(record['PING_TIMEOUT_SEC'], `${label}.PING_TIMEOUT_SEC`),
        STUCK_STATE_TIMEOUT_SEC: readNonNegativeNumber(record['STUCK_STATE_TIMEOUT_SEC'], `${label}.STUCK_STATE_TIMEOUT_SEC`),
        PENDING_STARTUP_TASK_TIMEOUT_SEC: readNonNegativeNumber(record['PENDING_STARTUP_TASK_TIMEOUT_SEC'], `${label}.PENDING_STARTUP_TASK_TIMEOUT_SEC`),
        RECOVERY_TIMEOUT_SEC: readNonNegativeNumber(record['RECOVERY_TIMEOUT_SEC'], `${label}.RECOVERY_TIMEOUT_SEC`),
        FAILURE_WINDOW_SEC: readNonNegativeNumber(record['FAILURE_WINDOW_SEC'], `${label}.FAILURE_WINDOW_SEC`),
        MAX_RECOVERY_ATTEMPTS: readRequiredNonNegativeIntegerValue(record['MAX_RECOVERY_ATTEMPTS'], `${label}.MAX_RECOVERY_ATTEMPTS`),
        PLANNER_WORKER_COUNT: readRequiredNonNegativeIntegerValue(record['NUM_PLANNER_WORKERS'], `${label}.NUM_PLANNER_WORKERS`),
        FAIR_DISPATCH_ENABLED: readRequiredBooleanValue(record['FAIR_DISPATCH_ENABLED'], `${label}.FAIR_DISPATCH_ENABLED`),
        FAIR_DISPATCH_MAX_PER_PLUGIN: readRequiredNonNegativeIntegerValue(record['FAIR_DISPATCH_MAX_PER_PLUGIN'], `${label}.FAIR_DISPATCH_MAX_PER_PLUGIN`),
        VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC: readNonNegativeNumber(record['VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC'], `${label}.VIRTUAL_MODEL_FAILOVER_COOLDOWN_SEC`),
        MAX_CONCURRENT_TASKS_PER_PLUGIN: {
            DEFAULT: readRequiredNonNegativeIntegerValue(taskLimits['DEFAULT'], `${label}.MAX_CONCURRENT_TASKS_PER_PLUGIN.DEFAULT`),
            PER_PLUGIN: readNonNegativeIntegerRecord(taskLimits['PER_PLUGIN'], `${label}.MAX_CONCURRENT_TASKS_PER_PLUGIN.PER_PLUGIN`)
        },
        COMMAND_TIMEOUTS_SEC: {
            PLUGIN_STOP: readNonNegativeNumber(timeouts['PLUGIN_STOP'], `${label}.COMMAND_TIMEOUTS_SEC.PLUGIN_STOP`),
            PLUGIN_LOAD_MODEL: readNonNegativeNumber(timeouts['PLUGIN_LOAD_MODEL'], `${label}.COMMAND_TIMEOUTS_SEC.PLUGIN_LOAD_MODEL`)
        }
    };
};

const decodeRoutingConfig = (value: JsonValue | undefined): RoutingConfigResponse => {
    const label = 'Routing config response';
    const record = requireRecord(value, label);
    return {
        maxConcurrentPlugins: readRequiredNonNegativeIntegerValue(record['max_concurrent_plugins'], `${label}.max_concurrent_plugins`),
        taskQueueMaxSize: readRequiredNonNegativeIntegerValue(record['task_queue_max_size'], `${label}.task_queue_max_size`),
        schedulerSafetyNetDelaySec: readNonNegativeNumber(record['scheduler_safety_net_delay_sec'], `${label}.scheduler_safety_net_delay_sec`),
        durableQueueLeaseTtlSec: readNonNegativeNumber(record['durable_queue_lease_ttl_sec'], `${label}.durable_queue_lease_ttl_sec`),
        durableQueueRecoverySweepSec: readNonNegativeNumber(record['durable_queue_recovery_sweep_sec'], `${label}.durable_queue_recovery_sweep_sec`),
        durableQueueHardLimitTasks: readRequiredNonNegativeIntegerValue(record['durable_queue_hard_limit_tasks'], `${label}.durable_queue_hard_limit_tasks`),
        minFreeDiskBytesForAccept: readRequiredNonNegativeIntegerValue(record['min_free_disk_bytes_for_accept'], `${label}.min_free_disk_bytes_for_accept`),
        pluginPrefetchWindowDefault: readRequiredNonNegativeIntegerValue(record['plugin_prefetch_window_default'], `${label}.plugin_prefetch_window_default`),
        standardPriorityAgingSec: readNonNegativeNumber(record['standard_priority_aging_sec'], `${label}.standard_priority_aging_sec`),
        flexPriorityAgingSec: readNonNegativeNumber(record['flex_priority_aging_sec'], `${label}.flex_priority_aging_sec`),
        cancelOnClientDisconnect: readRequiredBooleanValue(record['cancel_on_client_disconnect'], `${label}.cancel_on_client_disconnect`),
        httpAsyncAcceptDefault: readRequiredBooleanValue(record['http_async_accept_default'], `${label}.http_async_accept_default`),
        acceptanceDbBusyTimeoutSec: readNonNegativeNumber(record['acceptance_db_busy_timeout_sec'], `${label}.acceptance_db_busy_timeout_sec`),
        inferenceTaskRetentionDays: readRequiredNonNegativeIntegerValue(record['inference_task_retention_days'], `${label}.inference_task_retention_days`),
        ownerRunningLimitsDefault: readRequiredNonNegativeIntegerValue(record['owner_running_limits_default'], `${label}.owner_running_limits_default`),
        ownerRunningLimitsByOwnerType: readNonNegativeIntegerRecord(record['owner_running_limits_by_owner_type'], `${label}.owner_running_limits_by_owner_type`),
        deduplicationEnabled: readRequiredBooleanValue(record['deduplication_enabled'], `${label}.deduplication_enabled`),
        deduplicationKeys: readStringArray(record['deduplication_keys'], `${label}.deduplication_keys`),
        promptQueuing: readRequiredBooleanValue(record['prompt_queuing'], `${label}.prompt_queuing`),
        queuePromptSlotLimit: readRequiredNonNegativeIntegerValue(record['queue_prompt_slot_limit'], `${label}.queue_prompt_slot_limit`),
        fairTaskRotation: readRequiredBooleanValue(record['fair_task_rotation'], `${label}.fair_task_rotation`),
        virtualModels: decodeVirtualModels(record['virtual_models'], `${label}.virtual_models`),
        failovers: decodeFailovers(record['failovers'], `${label}.failovers`),
        healthChecks: decodeRoutingHealthChecks(record['health_checks'])
    };
};

const decodeRoutingConfigSnapshot = (value: ApiResponsePayload): RoutingConfigSnapshot => {
    const record: JsonObject = requireRecord(value, 'Routing config snapshot');
    return {
        virtualModels: decodeVirtualModels(record['virtual_models'], 'Routing config snapshot.virtual_models'),
        failovers: decodeFailovers(record['failovers'], 'Routing config snapshot.failovers'),
        routingConfig: decodeRoutingConfig(record['routing_config'])
    };
};

export { decodeRoutingConfigSnapshot };
export type { RoutingConfigResponse, RoutingConfigSnapshot, RoutingFailover, RoutingHealthChecks };
