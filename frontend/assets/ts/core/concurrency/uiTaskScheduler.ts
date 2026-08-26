/* SoAI - Shared concurrency UI task scheduler [frontend/assets/ts/core/concurrency/uiTaskScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isThenable } from '@core/typeGuards.ts';

type UiTaskPolicy = 'serialize' | 'latest-wins' | 'start-latest' | 'drop-if-busy';

type UiTaskRoute = {
    key: string;
    policy: UiTaskPolicy;
};

type UiTaskRouteResolver = (operationId: string) => UiTaskRoute;

interface UiTaskSchedulerHost {
    runWithBoundary<T>(operationId: string, task: () => Promise<T>): Promise<T>;
    logWarning(message: string, error: Error): void;
}

interface UiTaskScheduler {
    run(operationId: string, task: () => Promise<void> | void): void;
    runAsync(operationId: string, task: () => Promise<void> | void): Promise<void>;
    runResult<T>(operationId: string, task: () => Promise<T> | T): Promise<T | undefined>;
    dispose(): void;
}

const normalizeRuntimeError = (error: Error): Error => {
    return ensureError(error);
};

class UiTaskSchedulerImpl implements UiTaskScheduler {
    readonly #host: UiTaskSchedulerHost;
    readonly #resolveRoute: UiTaskRouteResolver;
    readonly #queueByKey: Map<string, Promise<void>> = new Map();
    readonly #latestTokenByKey: Map<string, number> = new Map();

    constructor(host: UiTaskSchedulerHost, resolveRoute: UiTaskRouteResolver) {
        this.#host = host;
        this.#resolveRoute = resolveRoute;
    }

    run(operationId: string, task: () => Promise<void> | void): void {
        void this.runAsync(operationId, task).catch((error): void => {
            this.#host.logWarning(`UI task scheduling failed: ${operationId}`, normalizeRuntimeError(error));
        });
    }

    runAsync(operationId: string, task: () => Promise<void> | void): Promise<void> {
        return this.#scheduleTask(operationId, task, { propagateErrors: false }).then((): void => {});
    }

    runResult<T>(operationId: string, task: () => Promise<T> | T): Promise<T | undefined> {
        return this.#scheduleTask(operationId, task, { propagateErrors: true });
    }

    #scheduleTask<T>(operationId: string, task: () => Promise<T> | T, options: { propagateErrors: boolean }): Promise<T | undefined> {
        const route = this.#resolveRoute(operationId);
        const hasPending = this.#queueByKey.has(route.key);
        if (route.policy === 'drop-if-busy' && hasPending) {
            return this.#resolveSkippedTask<T>();
        }

        if (route.policy === 'start-latest') {
            return this.#runStartLatestTask(route.key, operationId, task, options);
        }

        const previousCandidate = this.#queueByKey.get(route.key);
        const token = route.policy === 'latest-wins' ? this.#nextToken(route.key) : null;

        const execute = async (): Promise<T | undefined> => {
            if (token !== null && this.#latestTokenByKey.get(route.key) !== token) {
                return;
            }
            return await this.#host.runWithBoundary(operationId, async (): Promise<T | undefined> => {
                if (token !== null && this.#latestTokenByKey.get(route.key) !== token) {
                    return;
                }
                const taskResult = task();
                if (isThenable(taskResult)) {
                    return await taskResult;
                }
                return taskResult;
            });
        };

        const chained = (() => {
            if (previousCandidate === undefined) {
                return execute();
            }
            return previousCandidate
                .catch((error): void => {
                    this.#host.logWarning(`Recovered UI queue after failure: ${route.key}`, normalizeRuntimeError(error));
                })
                .then(execute);
        })();

        const result = options.propagateErrors ? chained : this.#recoverFailedTask(operationId, chained);

        let tracked: Promise<void>;
        tracked = result
            .catch((error): void => {
                this.#host.logWarning(`UI task failed: ${operationId}`, normalizeRuntimeError(error));
            })
            .then((): void => {})
            .finally((): void => {
                if (this.#queueByKey.get(route.key) === tracked) {
                    this.#queueByKey.delete(route.key);
                }
                if (token !== null && this.#latestTokenByKey.get(route.key) === token) {
                    this.#latestTokenByKey.delete(route.key);
                }
            });

        this.#queueByKey.set(route.key, tracked);
        return result;
    }

    async #resolveSkippedTask<T>(): Promise<T | undefined> {
        return undefined;
    }

    async #recoverFailedTask<T>(operationId: string, task: Promise<T | undefined>): Promise<T | undefined> {
        try {
            return await task;
        } catch (error) {
            this.#host.logWarning(`UI task failed: ${operationId}`, ensureError(error));
        }
        return await this.#resolveSkippedTask<T>();
    }

    dispose(): void {
        this.#queueByKey.clear();
        this.#latestTokenByKey.clear();
    }

    #runStartLatestTask<T>(operationKey: string, operationId: string, task: () => Promise<T> | T, options: { propagateErrors: boolean }): Promise<T | undefined> {
        const token = this.#nextToken(operationKey);
        const execute = async (): Promise<T | undefined> => {
            if (this.#latestTokenByKey.get(operationKey) !== token) {
                return;
            }
            return await this.#host.runWithBoundary(operationId, async (): Promise<T | undefined> => {
                if (this.#latestTokenByKey.get(operationKey) !== token) {
                    return;
                }
                const taskResult = task();
                if (isThenable(taskResult)) {
                    return await taskResult;
                }
                return taskResult;
            });
        };
        const result = options.propagateErrors ? execute() : this.#recoverFailedTask(operationId, execute());
        let tracked: Promise<void>;
        tracked = result
            .catch((error): void => {
                this.#host.logWarning(`UI task failed: ${operationId}`, normalizeRuntimeError(error));
            })
            .then((): void => {})
            .finally((): void => {
                if (this.#queueByKey.get(operationKey) === tracked) {
                    this.#queueByKey.delete(operationKey);
                }
                if (this.#latestTokenByKey.get(operationKey) === token) {
                    this.#latestTokenByKey.delete(operationKey);
                }
            });
        this.#queueByKey.set(operationKey, tracked);
        return result;
    }

    #nextToken(queueKey: string): number {
        const currentToken = this.#latestTokenByKey.get(queueKey);
        const nextToken = (currentToken === undefined ? 0 : currentToken) + 1;
        this.#latestTokenByKey.set(queueKey, nextToken);
        return nextToken;
    }
}

const createUiTaskScheduler = (host: UiTaskSchedulerHost, resolveRoute: UiTaskRouteResolver): UiTaskScheduler => {
    return new UiTaskSchedulerImpl(host, resolveRoute);
};

export { createUiTaskScheduler };
export type { UiTaskPolicy, UiTaskRoute, UiTaskRouteResolver, UiTaskScheduler, UiTaskSchedulerHost };
