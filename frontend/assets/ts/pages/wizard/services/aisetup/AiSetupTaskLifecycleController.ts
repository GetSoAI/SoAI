/* SoAI - Wizard task attempt ownership and cancellation [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupTaskLifecycleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isMutationAcceptanceRecoveryRequiredError } from '@core/realtime/streammanager/actions/mutationAcceptanceRecovery.ts';
import { isTerminalTaskStatus } from '@core/tasks/operationPayloads.ts';
import type { AiSetupModel } from '@core/storage/aisetup/aiSetupTypes.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { AiSetupOperationsManagerHost } from '@pages/wizard/services/aisetup/contracts.ts';
import { withAcceptedLocalDownload } from '@pages/wizard/services/aisetup/state.ts';
import { normalizeOperationError } from '@core/operationErrorNotifier.ts';
import { settleTrackedTaskStream, type TrackedTaskStreamTracker } from '@core/tasks/trackedTaskStream.ts';
import type { SettledTaskResult } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import { getWebUiUserCancellationReason } from '@core/tasks/cancellationReasons.ts';

interface AiSetupTaskAttempt {
    controller: AbortController;
    stream: StreamActionHandle | null;
    cancellation: ReturnType<typeof createDeferred<void>> | null;
}

class AiSetupTaskLifecycleController {
    #disposed = false;
    readonly #attempts = new Map<string, AiSetupTaskAttempt>();

    begin(key: string): AiSetupTaskAttempt {
        if (this.#attempts.has(key)) throw new Error('Wizard task already has an active attempt');
        const attempt: AiSetupTaskAttempt = { controller: new AbortController(), stream: null, cancellation: null };
        this.#attempts.set(key, attempt);
        return attempt;
    }

    attach(key: string, stream: StreamActionHandle, onAccepted?: (taskId: string) => void): void {
        const attempt = this.#attempts.get(key);
        if (attempt === undefined) {
            stream.close?.();
            return;
        }
        attempt.stream = stream;
        if (onAccepted !== undefined) {
            void stream.accepted?.then(onAccepted).catch((error) => errorHandler.warn('WizardAiSetup', 'Task acceptance was not confirmed', ensureError(error)));
        }
        if (attempt.cancellation !== null) this.#dispatch(attempt);
        if (this.#disposed) stream.close?.();
    }

    cancel(key: string): Promise<void> | undefined {
        const attempt = this.#attempts.get(key);
        if (attempt === undefined) return;
        if (attempt.cancellation !== null) return attempt.cancellation.promise;
        const cancellation = createDeferred<void>();
        attempt.cancellation = cancellation;
        attempt.controller.abort();
        if (attempt.stream !== null) this.#dispatch(attempt);
        return cancellation.promise;
    }

    finish(key: string): void {
        const attempt = this.#attempts.get(key);
        this.#attempts.delete(key);
        attempt?.cancellation?.resolve();
    }

    dispose(): void {
        this.#disposed = true;
        for (const attempt of this.#attempts.values()) attempt.stream?.close?.();
    }

    async settle(stream: StreamActionHandle, keyPrefix: string, failMessage: string, tracker: TrackedTaskStreamTracker): Promise<SettledTaskResult> {
        try {
            const settled = await settleTrackedTaskStream({ tracker, stream, keyPrefix, failMessage });
            if (settled.detached) return 'detached';
            return settled.cancelled ? 'cancelled' : 'succeeded';
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('WizardAiSetup', `Tracked ${keyPrefix} task did not complete`, runtimeError);
            return normalizeOperationError(runtimeError)?.isInsufficientDiskSpace === true ? 'failed_disk' : 'failed';
        }
    }

    async recoverDownload(error: Error, itemId: string, host: Pick<AiSetupOperationsManagerHost, 'getSetup' | 'updateSetup' | 'streaming'>, attach: (item: AiSetupModel, taskId: string, cancel: boolean) => void, cancelled: boolean): Promise<boolean> {
        const failure = normalizeOperationError(error);
        const uncertain = isMutationAcceptanceRecoveryRequiredError(error);
        const taskId = uncertain ? error.requestId : failure?.code === 'mutation_conflict' ? failure.taskId : null;
        if (taskId === null) return false;
        const task = await host.streaming.runtime().tasks.readTaskSnapshot(taskId);
        if (task === null || task.taskType !== 'model_download' || this.#disposed || host.getSetup().committedLocalItemId !== itemId) return false;
        const pluginName = toTrimmedString(task.metadata['plugin_name']);
        const repositoryId = toTrimmedString(task.metadata['model_id']);
        const artifactReference = toTrimmedString(task.metadata['quantization']);
        if (!pluginName || !repositoryId || !artifactReference) throw new Error('Accepted download snapshot is missing its artifact identity');
        const retryable = isTerminalTaskStatus(task.status) && task.status !== 'completed';
        host.updateSetup((setup) => withAcceptedLocalDownload(setup, { pluginName, repositoryId, artifactReference, artifactName: artifactReference, catalogId: null }, taskId, retryable));
        if (retryable) return false;
        const item = host.getSetup().models.find((model) => model.downloadTaskId === taskId && !model.excluded);
        if (item === undefined) throw new Error('Accepted download selection could not be reconciled');
        attach(item, taskId, uncertain && cancelled);
        return true;
    }

    #dispatch(attempt: AiSetupTaskAttempt): void {
        const cancellation = attempt.cancellation;
        const stream = attempt.stream;
        if (cancellation === null || stream === null) return;
        const request = stream.requestCancellation;
        if (request === undefined) {
            cancellation.reject(new Error('Task cancellation ownership is unavailable'));
            attempt.cancellation = null;
            return;
        }
        void request(getWebUiUserCancellationReason()).then(
            () => cancellation.resolve(),
            (error) => {
                if (attempt.cancellation === cancellation) attempt.cancellation = null;
                cancellation.reject(error);
            }
        );
    }
}

export { AiSetupTaskLifecycleController };
