/* SoAI - Models feature shared model download run [frontend/assets/ts/features/models/downloads/modelDownloadRun.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMutationAcceptanceRecoveryRequiredError } from '@core/realtime/streammanager/actions/mutationAcceptanceRecovery.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { DownloadParameters } from '@core/modelactions/contracts.ts';
import { normalizeOperationError } from '@core/operationErrorNotifier.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import { settleTrackedTaskStream, type TrackedTaskStreamTracker } from '@core/tasks/trackedTaskStream.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import { admitModelDownload } from '@features/models/downloads/modelDownloadOperations.ts';
import { MODEL_DOWNLOAD_OPERATION_TYPE } from '@features/models/modelDownloadOperation.ts';

interface ModelDownloadRunOptions {
    request: DownloadParameters;
    signal?: AbortSignal;
    startDownload: (request: DownloadParameters, options: { handlers: StreamActionHandlers; signal?: AbortSignal }) => Promise<StreamActionHandle>;
    handlers: StreamActionHandlers;
    tracker: TrackedTaskStreamTracker;
    failMessage: string;
    onAdmitted?: () => void;
    onStarted?: (stream: StreamActionHandle) => void;
}

type ModelDownloadOutcome = { status: 'rejected'; reason: 'max_concurrent' | 'already_downloading' } | { status: 'finished'; isCompleteEvent: boolean; message: string } | { status: 'cancelled' | 'detached'; message: string } | { status: 'failed'; error: Error; insufficientDiskSpace: boolean };

const runModelDownload = async (options: ModelDownloadRunOptions): Promise<ModelDownloadOutcome> => {
    const admission = admitModelDownload(options.request);
    if (admission.status === 'rejected') {
        return admission;
    }
    try {
        options.onAdmitted?.();
        const stream = await options.startDownload(options.request, { handlers: options.handlers, ...(options.signal === undefined ? {} : { signal: options.signal }) });
        options.onStarted?.(stream);
        const settled = await settleTrackedTaskStream({
            tracker: options.tracker,
            stream,
            keyPrefix: MODEL_DOWNLOAD_OPERATION_TYPE,
            failMessage: options.failMessage
        });
        if (settled.cancelled) return { status: 'cancelled', message: settled.message };
        if (settled.detached) return { status: 'detached', message: settled.message };
        return { status: 'finished', isCompleteEvent: settled.isCompleteEvent, message: settled.message };
    } catch (error) {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError)) return { status: 'cancelled', message: '' };
        if (normalizeOperationError(runtimeError)?.code !== 'mutation_conflict' && !isMutationAcceptanceRecoveryRequiredError(runtimeError)) errorHandler.error('ModelDownload', 'Model download failed', runtimeError);
        return { status: 'failed', error: runtimeError, insufficientDiskSpace: normalizeOperationError(runtimeError)?.isInsufficientDiskSpace === true };
    } finally {
        admission.release();
    }
};

export { runModelDownload };
export type { ModelDownloadOutcome, ModelDownloadRunOptions };
