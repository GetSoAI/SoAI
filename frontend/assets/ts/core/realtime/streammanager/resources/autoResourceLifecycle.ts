/* SoAI - Shared realtime auto resource lifecycle [frontend/assets/ts/core/realtime/streammanager/resources/autoResourceLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError } from '@core/apiError.ts';
import { coerceErrorMessage } from '@core/errors/coerce.ts';
import { raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { getAutoResourceState, setAutoResourceState } from '@core/realtime/streammanager/autoresources/state.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface AutoResourceStartEntry {
    name: string;
    autoStart: boolean;
    status: string;
    pending: boolean;
}

interface StartAutoResourcesDependencies {
    isMaintenanceActive: () => boolean;
    resources: readonly AutoResourceStartEntry[];
    ensureStart: (name: string, options: { signal?: AbortSignal | undefined }) => Promise<JsonValue | null>;
    signal?: AbortSignal | undefined;
}

const startAutoResources = async (dependencies: StartAutoResourcesDependencies): Promise<(JsonValue | null)[]> => {
    if (dependencies.isMaintenanceActive()) {
        return [];
    }
    throwIfAborted(dependencies.signal);

    const tasks: Array<Promise<JsonValue | null>> = [];
    let networkFailure = false;
    dependencies.resources.forEach((resource) => {
        if (!resource.autoStart) return;
        if (resource.status === 'ready' || resource.pending || resource.status === 'initializing') return;
        tasks.push(
            dependencies.ensureStart(resource.name, { signal: dependencies.signal }).catch((error) => {
                if (isNetworkError(error)) {
                    networkFailure = true;
                    const message = coerceErrorMessage(error);
                    setAutoResourceState({ status: 'offline', error: { resource: resource.name, message } });
                }
                throw error;
            })
        );
    });

    if (!tasks.length) {
        if (getAutoResourceState().status !== 'offline') {
            setAutoResourceState({ status: 'ready', error: null });
        }
        return [];
    }

    setAutoResourceState({ status: 'starting', error: null });
    try {
        const resultTask = Promise.all(tasks);
        const results = dependencies.signal ? await raceWithAbortSignal(resultTask, dependencies.signal) : await resultTask;
        if (!networkFailure) {
            setAutoResourceState({ status: 'ready', error: null });
        }
        return results;
    } catch (error) {
        if (!networkFailure) {
            const message = coerceErrorMessage(error, 'Unknown error');
            setAutoResourceState({ status: 'error', error: { message } });
        }
        throw error;
    }
};

export { startAutoResources };
