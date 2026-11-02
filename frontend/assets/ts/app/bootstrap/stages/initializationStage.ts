/* SoAI - Frontend initialization stage failure context [frontend/assets/ts/app/bootstrap/stages/initializationStage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { getErrorReference } from '@core/errors/reference.ts';

type InitializationStage = 'entrypoint' | 'criticalServices' | 'authentication' | 'session' | 'routeRendering' | 'background';

interface InitializationFailure {
    stage: InitializationStage | null;
    reference: string;
}

const failureStages = new WeakMap<Error, InitializationStage>();

const runInitializationStage = async <T>(stage: InitializationStage, operation: () => T | Promise<T>): Promise<T> => {
    try {
        return await operation();
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!failureStages.has(runtimeError)) failureStages.set(runtimeError, stage);
        throw runtimeError;
    }
};

const describeInitializationFailure = (error: Error): InitializationFailure => {
    return { stage: failureStages.get(error) ?? null, reference: getErrorReference(error) };
};

const reportInitializationFailure = (module: string, message: string, failure: Error, reported: Error = failure): void => {
    const { stage, reference } = describeInitializationFailure(failure);
    errorHandler.error(module, message, reported, { stage: stage ?? 'unknown', context: { reference } });
};

const isIntentionalInitializationCancellation = <T>(error: T): boolean => isAbortError(error) || isLifecycleCancellationError(error);

export { describeInitializationFailure, isIntentionalInitializationCancellation, reportInitializationFailure, runInitializationStage };
export type { InitializationFailure, InitializationStage };
