/* SoAI - Dashboard page live data [frontend/assets/ts/pages/dashboard/controllers/dashboardLiveData.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isObject } from '@core/typeGuards.ts';
import { isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isJsonObjectMapValue } from '@core/types/runtimeCollectionGuards.ts';
import type { HardwareData, HardwareSnapshot } from '@features/hardware/public.ts';
import { resolveDashboardStatusMetrics } from '@pages/dashboard/mappers/statusMetricsDomain.ts';
import type { DashboardState } from '@pages/dashboard/state/dashboardStateModel.ts';

type DashboardLiveDataKey = 'status' | 'metrics' | 'hardware' | 'plugins' | 'models';
type DashboardSectionId = 'status' | 'productCapabilities' | 'requests' | 'hardwareWidgets' | 'network' | 'storage' | 'plugins' | 'models';

interface DashboardLiveDataContext {
    state: DashboardState;
    rawHardwareSnapshot: HardwareSnapshot | HardwareData | null;
    dataReceived: Set<DashboardLiveDataKey>;
    sectionDataFingerprints: Map<DashboardSectionId, string>;
}

const SECTION_UPDATE_MAP: Readonly<Record<DashboardLiveDataKey, readonly DashboardSectionId[]>> = Object.freeze({
    status: ['status'],
    metrics: ['status', 'requests'],
    hardware: ['hardwareWidgets', 'network', 'storage'],
    plugins: ['plugins', 'status'],
    models: ['models', 'status']
});

const collectPluginRequestFingerprint = (plugins: JsonValue | null | undefined): JsonObject => {
    const output: JsonObject = {};
    if (!isObject(plugins)) {
        return output;
    }
    for (const [name, plugin] of Object.entries(plugins)) {
        if (!isObject(plugin)) {
            continue;
        }
        const requestsTotal = plugin['requestsTotal'];
        if (isJsonValue(requestsTotal)) {
            output[name] = requestsTotal;
        }
    }
    return output;
};

const computeDashboardSectionFingerprint = (context: DashboardLiveDataContext, sectionId: DashboardSectionId): string => {
    switch (sectionId) {
        case 'status': {
            const statusMetrics = resolveDashboardStatusMetrics(context.state.metrics, context.state.plugins.length, context.state.models.length);
            return JSON.stringify({
                installedPlugins: statusMetrics.installedPlugins,
                installedModels: statusMetrics.installedModels,
                totalTokens: statusMetrics.totalTokens,
                uptimeSeconds: statusMetrics.uptimeSeconds,
                completed: statusMetrics.completedFingerprintValue,
                failed: statusMetrics.failedFingerprintValue
            });
        }
        case 'productCapabilities':
            return '';
        case 'requests': {
            const metricsObject = isObject(context.state.metrics) ? context.state.metrics : {};
            const director = metricsObject['director'];
            const directorObject = isObject(director) ? director : {};
            const requestsByModel = directorObject['requestsByModel'];
            const requestsByVirtualModel = directorObject['requestsByVirtualModel'];
            return JSON.stringify({
                requestsByModel: isObject(requestsByModel) ? requestsByModel : {},
                requestsByVirtualModel: isObject(requestsByVirtualModel) ? requestsByVirtualModel : {},
                pluginRequests: collectPluginRequestFingerprint(metricsObject['plugins'])
            });
        }
        case 'plugins':
            return JSON.stringify(
                context.state.plugins.map((plugin: JsonValue | null) => {
                    const pluginObject = isObject(plugin) ? plugin : {};
                    return { name: pluginObject['name'], state: pluginObject['state'], isEnabled: pluginObject['isEnabled'] };
                })
            );
        case 'models':
            return JSON.stringify(
                context.state.models.map((model: JsonValue | null) => {
                    const modelObject = isObject(model) ? model : {};
                    return { id: modelObject['id'], status: modelObject['status'], loaded: modelObject['loaded'] };
                })
            );
        case 'hardwareWidgets':
        case 'network':
        case 'storage': {
            const snapshot = context.rawHardwareSnapshot;
            if (!isObject(snapshot)) {
                return '';
            }
            const snapshotObject = snapshot;
            if (sectionId === 'network') {
                const network = isObject(snapshotObject['network']) ? snapshotObject['network'] : null;
                const interfaces = network?.['interfaces'];
                const networkSpeed = snapshotObject['networkSpeed'];
                return JSON.stringify({
                    interfaces: isArray(interfaces) ? interfaces : [],
                    speed: isJsonObjectMapValue(networkSpeed) ? networkSpeed : {}
                });
            }
            if (sectionId === 'storage') {
                const partitions = snapshotObject['disk'];
                return isArray(partitions) ? JSON.stringify(partitions) : '';
            }
            const hardware = snapshotObject['gpu'];
            const hardwareObject = isObject(hardware) ? hardware : {};
            const cpus = snapshotObject['cpus'];
            const network = snapshotObject['network'];
            const networkObject = isObject(network) ? network : {};
            const interfaces = networkObject['interfaces'];
            const networkSpeed = snapshotObject['networkSpeed'];
            return JSON.stringify({
                cpus: isArray(cpus) ? cpus : [],
                gpus: isArray(hardwareObject['gpus']) ? hardwareObject['gpus'] : [],
                memory: isObject(snapshotObject['memory']) ? snapshotObject['memory'] : {},
                network: isArray(interfaces) ? interfaces : [],
                networkSpeed: isJsonObjectMapValue(networkSpeed) ? networkSpeed : {}
            });
        }
    }
};

const applyDashboardLiveDataUpdate = (context: DashboardLiveDataContext, type: DashboardLiveDataKey, payload: JsonValue | null): DashboardSectionId[] => {
    switch (type) {
        case 'status':
            break;
        case 'metrics':
            context.state.metrics = isObject(payload) ? payload : {};
            break;
        case 'hardware': {
            const rawSnapshot = isObject(payload) ? payload : null;
            context.rawHardwareSnapshot = rawSnapshot;
            break;
        }
        case 'plugins':
            context.state.plugins = isArray(payload) ? payload : [];
            break;
        case 'models':
            context.state.models = isArray(payload) ? payload : [];
            break;
    }

    context.dataReceived.add(type);
    const updatedSections: DashboardSectionId[] = [];
    for (const sectionId of SECTION_UPDATE_MAP[type]) {
        const newFingerprint = computeDashboardSectionFingerprint(context, sectionId);
        const previous = context.sectionDataFingerprints.get(sectionId);
        if (newFingerprint === previous) {
            continue;
        }
        context.sectionDataFingerprints.set(sectionId, newFingerprint);
        updatedSections.push(sectionId);
    }
    return updatedSections;
};

export { applyDashboardLiveDataUpdate, computeDashboardSectionFingerprint, SECTION_UPDATE_MAP };
export type { DashboardLiveDataContext, DashboardLiveDataKey, DashboardSectionId };
