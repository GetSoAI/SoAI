/* SoAI - Models feature model download operations [frontend/assets/ts/features/models/downloads/modelDownloadOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { TaskOperationEntry } from '@core/tasks/protocols.ts';
import { MODEL_DOWNLOAD_OPERATION_FILTER } from '@features/models/modelDownloadOperation.ts';

interface ModelDownloadRequestSignature {
    plugin?: string | undefined;
    modelId?: string | undefined;
    universalId?: string | undefined;
    quantization?: string | undefined;
}

type ModelDownloadAdmission = { status: 'admitted'; release: () => void } | { status: 'rejected'; reason: 'max_concurrent' | 'already_downloading' };

const MAX_CONCURRENT_MODEL_DOWNLOADS = 5;

const pendingModelDownloadSignatures = new Set<string>();

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

const findActiveModelDownloadOperation = (request: ModelDownloadRequestSignature): TaskOperationEntry | null => getActiveModelDownloadOperations().find((operation) => operationMatchesRequest(operation, request)) ?? null;

const countActiveModelDownloads = (): number => {
    const operations = getActiveModelDownloadOperations();
    const operationSignatures = new Set(operations.map((operation) => buildOperationSignature(operation)).filter((signature) => signature));
    let pendingCount = 0;
    for (const signature of pendingModelDownloadSignatures) {
        if (!operationSignatures.has(signature)) {
            pendingCount += 1;
        }
    }
    return operations.length + pendingCount;
};

const admitModelDownload = (request: ModelDownloadRequestSignature): ModelDownloadAdmission => {
    if (countActiveModelDownloads() >= MAX_CONCURRENT_MODEL_DOWNLOADS) {
        return { status: 'rejected', reason: 'max_concurrent' };
    }
    const signature = buildRequestSignature(request);
    if (pendingModelDownloadSignatures.has(signature) || findActiveModelDownloadOperation(request) !== null) {
        return { status: 'rejected', reason: 'already_downloading' };
    }
    pendingModelDownloadSignatures.add(signature);
    let released = false;
    return {
        status: 'admitted',
        release: (): void => {
            if (released) return;
            released = true;
            pendingModelDownloadSignatures.delete(signature);
        }
    };
};

export { admitModelDownload, buildRequestSignature, countActiveModelDownloads, findActiveModelDownloadOperation, getActiveModelDownloadOperations, operationMatchesRequest };
export type { ModelDownloadAdmission, ModelDownloadRequestSignature };
