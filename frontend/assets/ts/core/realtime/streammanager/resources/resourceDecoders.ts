/* SoAI - Frontend realtime resource boundary decoders [frontend/assets/ts/core/realtime/streammanager/resources/resourceDecoders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeHardwareSnapshot } from '@core/api/contracts/hardwareContracts.ts';
import { decodeExternalProviderListResponse } from '@core/api/contracts/pluginProviderContracts.ts';
import { decodePromptListResponse } from '@core/api/contracts/promptContracts.ts';
import { decodeVirtualModelListResponse } from '@core/api/contracts/virtualModelContracts.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { normalizeFormattedModelListPayload } from '@core/models/modelRecordNormalization.ts';
import { parseStrictNotificationsListResponse } from '@core/notifications/listParsing.ts';
import { parsePluginsCollectionSnapshot } from '@core/plugins/collectionSnapshot.ts';
import { normalizeLogSnapshot } from '@core/realtime/streammanager/logSnapshotNormalization.ts';
import type { HardwareProcessRecord, HardwareProcessesResource, HardwareSnapshotResource, LogsResource, ModelsResource, NotificationsResource, PluginsResource, PromptsResource, ProvidersResource, RoutingConfigResource, VirtualModelsResource } from '@core/realtime/streammanager/resources/resourceValueContracts.ts';
import { isBoolean, isFiniteNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const requireJsonDomainValue = <DomainValue>(value: DomainValue, label: string): DomainValue & JsonValue => {
    if (!isJsonValue(value)) throw new TypeError(`${label} could not be represented as JSON`);
    return value;
};

const requireJsonObjectDomainValue = <DomainValue>(value: DomainValue, label: string): DomainValue & JsonObject => {
    if (!isJsonObject(value)) throw new TypeError(`${label} could not be represented as a JSON object`);
    return value;
};

const decodeModelsResource = (payload: JsonValue | null): ModelsResource => {
    if (payload === null) throw new TypeError('models.collection snapshot payload must not be null');
    const models = normalizeFormattedModelListPayload(payload, getLanguageService().getLocale());
    if (models === null) throw new TypeError('models.collection snapshot payload must be a model list or grouped model collection');
    return requireJsonDomainValue(models, 'models.collection');
};

const decodePluginsResource = (payload: JsonValue | null): PluginsResource => parsePluginsCollectionSnapshot(payload);

const decodePromptsResource = (payload: JsonValue | null): PromptsResource => requireJsonDomainValue(decodePromptListResponse(payload), 'prompts.collection');

const decodeProvidersResource = (payload: JsonValue | null): ProvidersResource => requireJsonDomainValue(decodeExternalProviderListResponse(payload), 'providers.collection');

const decodeHardwareSnapshotResource = (payload: JsonValue | null): HardwareSnapshotResource => requireJsonObjectDomainValue(decodeHardwareSnapshot(payload), 'hardware.snapshot');

const isHardwareSnapshotResource = (payload: JsonValue | null | undefined): payload is HardwareSnapshotResource => {
    return isJsonObject(payload) && isFiniteNumber(payload['timestampMs']) && isJsonObject(payload['summary']) && isJsonObject(payload['capabilities']);
};

function requireProcessNumber(record: JsonObject, key: string, index: number): number;
function requireProcessNumber(record: JsonObject, key: string, index: number, nullable: true): number | null;
function requireProcessNumber(record: JsonObject, key: string, index: number, nullable = false): number | null {
    const value = record[key];
    if (nullable && value === null) return null;
    if (!isFiniteNumber(value) || value < 0) throw new TypeError(`hardware.processes entry ${String(index)} ${key} must be a non-negative number`);
    return value;
}

const decodeHardwareProcess = (value: JsonValue, index: number): HardwareProcessRecord => {
    if (!isJsonObject(value)) throw new TypeError(`hardware.processes entry ${String(index)} must be an object`);
    const pid = requireProcessNumber(value, 'pid', index);
    const name = value['name'];
    const username = value['username'];
    const swapKnown = value['swapKnown'];
    if (!Number.isInteger(pid) || pid < 1) throw new TypeError(`hardware.processes entry ${String(index)} pid must be a positive integer`);
    if (!isString(name)) throw new TypeError(`hardware.processes entry ${String(index)} name must be a string`);
    if (!isString(username)) throw new TypeError(`hardware.processes entry ${String(index)} username must be a string`);
    if (!isBoolean(swapKnown)) throw new TypeError(`hardware.processes entry ${String(index)} swapKnown must be a boolean`);
    return {
        pid,
        name,
        username,
        cpuPercent: requireProcessNumber(value, 'cpuPercent', index),
        memoryMb: requireProcessNumber(value, 'memoryMb', index),
        swapMb: requireProcessNumber(value, 'swapMb', index, true),
        swapKnown,
        createTimeMs: requireProcessNumber(value, 'createTimeMs', index)
    };
};

const decodeHardwareProcessesResource = (payload: JsonValue | null): HardwareProcessesResource => {
    if (!Array.isArray(payload)) throw new TypeError('hardware.processes snapshot payload must be an array');
    return payload.map(decodeHardwareProcess);
};

const isHardwareProcessesResource = (payload: JsonValue | null): payload is HardwareProcessesResource => {
    return Array.isArray(payload) && payload.every((entry) => isJsonObject(entry) && isFiniteNumber(entry['pid']) && isString(entry['name']) && isString(entry['username']) && isFiniteNumber(entry['cpuPercent']) && isFiniteNumber(entry['memoryMb']) && (entry['swapMb'] === null || isFiniteNumber(entry['swapMb'])) && isBoolean(entry['swapKnown']) && isFiniteNumber(entry['createTimeMs']));
};

const decodeLogsResource = (payload: JsonValue | null): LogsResource => requireJsonObjectDomainValue(normalizeLogSnapshot(payload), 'system.logs.core');

const decodeNotificationsResource = (payload: JsonValue | null): NotificationsResource => requireJsonObjectDomainValue(parseStrictNotificationsListResponse(payload), 'webui.notifications');

const decodeRoutingConfigResource = (payload: JsonValue | null): RoutingConfigResource => {
    if (!isJsonObject(payload)) throw new TypeError('routing.config update payload must be an object');
    const decoded: RoutingConfigResource = {};
    const traceId = payload['trace_id'];
    const eventId = payload['event_id'];
    if (traceId !== undefined) {
        if (!isString(traceId)) throw new TypeError('routing.config trace_id must be a string');
        decoded.traceId = traceId;
    }
    if (eventId !== undefined) {
        if (!isString(eventId)) throw new TypeError('routing.config event_id must be a string');
        decoded.eventId = eventId;
    }
    if (payload['timestamp'] !== undefined) decoded.timestamp = payload['timestamp'];
    if (payload['virtual_models'] !== undefined) decoded.virtualModels = decodeVirtualModelsResource(payload['virtual_models'] ?? null);
    if (payload['failovers'] !== undefined) {
        const failovers = payload['failovers'];
        if (!Array.isArray(failovers) || !failovers.every(isJsonObject)) throw new TypeError('routing.config failovers must be an object array');
        decoded.failovers = failovers;
    }
    if (payload['routing_config'] !== undefined) {
        const routingConfig = payload['routing_config'];
        if (!isJsonObject(routingConfig)) throw new TypeError('routing.config routing_config must be an object');
        decoded.routingConfig = routingConfig;
    }
    return decoded;
};

const decodeVirtualModelsResource = (payload: JsonValue | null): VirtualModelsResource => requireJsonDomainValue(decodeVirtualModelListResponse(payload), 'routing.virtualModels');

export { decodeHardwareProcessesResource, decodeHardwareSnapshotResource, decodeLogsResource, decodeModelsResource, decodeNotificationsResource, decodePluginsResource, decodePromptsResource, decodeProvidersResource, decodeRoutingConfigResource, decodeVirtualModelsResource, isHardwareProcessesResource, isHardwareSnapshotResource };
