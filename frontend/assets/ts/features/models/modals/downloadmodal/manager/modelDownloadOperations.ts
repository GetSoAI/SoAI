/* SoAI - Models feature model download operations [frontend/assets/ts/features/models/modals/downloadmodal/manager/modelDownloadOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { TaskOperationEntry } from '@core/tasks/protocols.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { MODEL_DOWNLOAD_OPERATION_FILTER, MODEL_DOWNLOAD_OPERATION_TYPE } from '@features/models/modelDownloadOperation.ts';

interface ModelDownloadRequestSignature {
    plugin?: string | undefined;
    modelId?: string | undefined;
    universalId?: string | undefined;
    quantization?: string | undefined;
}

const buildRequestSignature = (request: ModelDownloadRequestSignature): string => {
    const universalId = toTrimmedString(request.universalId).toLowerCase();
    if (universalId) {
        return universalId;
    }
    return `${toTrimmedString(request.plugin).toLowerCase()}:${toTrimmedString(request.modelId).toLowerCase()}:${toTrimmedString(request.quantization).toLowerCase()}`;
};

const buildOperationSignature = (operation: TaskOperationEntry): string => {
    const meta = operation.meta ?? {};
    const universalId = toTrimmedString(meta['universalId']).toLowerCase();
    if (universalId) {
        return universalId;
    }
    return `${toTrimmedString(meta['plugin'] ?? meta['pluginName']).toLowerCase()}:${toTrimmedString(meta['modelId']).toLowerCase()}:${toTrimmedString(meta['quantization']).toLowerCase()}`;
};

const getActiveModelDownloadOperations = (): TaskOperationEntry[] => requireTaskOperationsApi().getOperations(MODEL_DOWNLOAD_OPERATION_FILTER);

const operationMatchesRequest = (operation: TaskOperationEntry, request: ModelDownloadRequestSignature): boolean => {
    const requestSignature = buildRequestSignature(request);
    return Boolean(requestSignature) && buildOperationSignature(operation) === requestSignature;
};

const countActiveModelDownloads = (runtime: DownloadModalManagerRuntime): number => {
    const operations = getActiveModelDownloadOperations();
    const operationSignatures = new Set(operations.map((operation) => buildOperationSignature(operation)).filter((signature) => signature));
    let pendingCount = 0;
    for (const signature of runtime.state.activeDownloadSignatures) {
        if (signature && !operationSignatures.has(signature)) {
            pendingCount += 1;
        }
    }
    return operations.length + pendingCount;
};

const hasActiveModelDownloads = (runtime: DownloadModalManagerRuntime): boolean => {
    return countActiveModelDownloads(runtime) > 0 || runtime.host.execution.requireStreamManager().hasActiveOperationsOfType(MODEL_DOWNLOAD_OPERATION_TYPE);
};

export { buildRequestSignature, countActiveModelDownloads, getActiveModelDownloadOperations, hasActiveModelDownloads, operationMatchesRequest };
export type { ModelDownloadRequestSignature };
