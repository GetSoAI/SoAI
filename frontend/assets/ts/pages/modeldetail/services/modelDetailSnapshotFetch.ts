/* SoAI - Model detail page services snapshot fetch [frontend/assets/ts/pages/modeldetail/services/modelDetailSnapshotFetch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { waitForResourceSnapshot } from '@core/realtime/resourceSnapshotWait.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { decodeModelDetailParameterPayload } from '@pages/modeldetail/mappers/ModelDetailParameterPayloadDomain.ts';
import type { ModelDetailParametersData } from '@pages/modeldetail/types.ts';

interface FetchModelSnapshotHost {
    modelId: string | null;
    streamManager: StreamRuntimeOwners;
    extractModelPayload(raw: JsonValue | null): ModelRecord | null;
}

interface FetchParametersSnapshotHost {
    modelId: string | null;
    model: ModelRecord | null;
}

const fetchModelSnapshotFromCollection = async (host: FetchModelSnapshotHost): Promise<ModelRecord> => {
    return waitForResourceSnapshot({
        host: {
            getResource: (resourceName) => host.streamManager.resources.getResource(resourceName),
            subscribe: (resourceName, listener, options) => host.streamManager.subscriptions.subscribeResourceState(resourceName, listener, options),
            extract: (raw) => host.extractModelPayload(raw ?? null)
        },
        resourceName: MODELS,
        timeoutMs: 5000,
        timeoutMessage: `Model ${host.modelId || 'unavailable'} not found in collection`,
        logContext: 'ModelDetailPage',
        logMetadata: { id: host.modelId }
    });
};

const resolveUniversalModelId = (host: FetchParametersSnapshotHost): string => {
    const model = host.model;
    if (isObject(model)) {
        const universalIdCandidate = model.universalId;
        if (isString(universalIdCandidate) && universalIdCandidate.trim()) {
            return universalIdCandidate.trim();
        }
    }
    throw new Error('ModelDetailPage requires model.universalId to load parameters');
};

const fetchParametersViaWebSocketSnapshot = async (host: FetchParametersSnapshotHost): Promise<ModelDetailParametersData> => {
    const universalId = resolveUniversalModelId(host);
    const payload = await requestWebSocketSnapshotRecord('models.parameters', { 'universal_id': universalId });
    return decodeModelDetailParameterPayload(payload);
};

export { fetchModelSnapshotFromCollection, fetchParametersViaWebSocketSnapshot };
export type { FetchModelSnapshotHost, FetchParametersSnapshotHost };
