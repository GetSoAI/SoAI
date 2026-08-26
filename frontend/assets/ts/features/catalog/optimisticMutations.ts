/* SoAI - Catalog optimistic mutation terminal ownership [frontend/assets/ts/features/catalog/optimisticMutations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OptimisticOperation, ResourceSnapshot } from '@core/data/clientdatahub/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import type { TaskTerminalEvent, TaskTerminalListener } from '@core/realtime/streammanager/types.ts';
import { toTrimmedString } from '@core/normalize.ts';

const GLOBALLY_RECONCILED_PLUGIN_MUTATION_TYPES = new Set(['backend-install', 'backend-remove', 'backend-update']);
const TERMINAL_ACCEPTANCE_JOIN_WINDOW_MS = 30_000;
const MAX_UNMATCHED_TERMINAL_TASKS = 128;

interface CatalogOptimisticMutationHub {
    beginOptimisticOperation(resource: string, operation: OptimisticOperation): ResourceSnapshot | void;
    markOptimisticOperationTerminal(resource: string, operationId: string, status: 'succeeded' | 'failed' | 'cancelled'): ResourceSnapshot | void;
    ensureResource(resource: string, force: boolean): Promise<ResourceSnapshot | void>;
}

interface CatalogOptimisticMutationDependencies {
    hub: CatalogOptimisticMutationHub;
    subscribeTerminalTasks(listener: TaskTerminalListener): () => void;
}

interface CatalogOptimisticMutations {
    begin(operation: OptimisticOperation): void;
    dispose(): void;
}

const createCatalogOptimisticMutations = (dependencies: CatalogOptimisticMutationDependencies): CatalogOptimisticMutations => {
    const operationIdsByTask = new Map<string, string>();
    const unmatchedTerminals = new Map<string, { event: TaskTerminalEvent; recordedAt: number }>();
    const pruneUnmatchedTerminals = (now: number): void => {
        for (const [taskId, terminal] of unmatchedTerminals) {
            if (now - terminal.recordedAt <= TERMINAL_ACCEPTANCE_JOIN_WINDOW_MS) break;
            unmatchedTerminals.delete(taskId);
        }
        while (unmatchedTerminals.size >= MAX_UNMATCHED_TERMINAL_TASKS) {
            const oldestTaskId = unmatchedTerminals.keys().next().value;
            if (typeof oldestTaskId !== 'string') break;
            unmatchedTerminals.delete(oldestTaskId);
        }
    };
    const settleTerminal = (event: TaskTerminalEvent): boolean => {
        const operationId = operationIdsByTask.get(event.taskId);
        if (!operationId) {
            performance.mark(`soai-audit:catalog-terminal-unmatched:${event.taskId}`);
            return false;
        }
        performance.mark(`soai-audit:catalog-terminal-matched:${event.taskId}`);
        operationIdsByTask.delete(event.taskId);
        const normalizedStatus = event.status.trim().toLowerCase();
        const status = event.success ? 'succeeded' : normalizedStatus === 'cancelled' ? 'cancelled' : 'failed';
        dependencies.hub.markOptimisticOperationTerminal(PLUGINS, operationId, status);
        const operationType = toTrimmedString(event.meta?.type);
        if (status === 'succeeded' && !GLOBALLY_RECONCILED_PLUGIN_MUTATION_TYPES.has(operationType)) {
            void dependencies.hub.ensureResource(PLUGINS, true).catch((error) => {
                errorHandler.warn('CatalogOptimisticMutations', 'Authoritative plugin reconciliation failed after task success', ensureError(error));
            });
        }
        return true;
    };
    const terminalListener: TaskTerminalListener = (event): void => {
        if (settleTerminal(event)) return;
        const now = performance.now();
        pruneUnmatchedTerminals(now);
        unmatchedTerminals.set(event.taskId, { event, recordedAt: now });
    };
    const unsubscribe = dependencies.subscribeTerminalTasks(terminalListener);
    return Object.freeze({
        begin: (operation: OptimisticOperation): void => {
            performance.mark(`soai-audit:catalog-begin:${operation.acceptedTaskId}`);
            const existingOperationId = operationIdsByTask.get(operation.acceptedTaskId);
            if (existingOperationId === operation.operationId) return;
            if (existingOperationId) throw new Error(`Accepted task ${operation.acceptedTaskId} already owns catalog optimism`);
            dependencies.hub.beginOptimisticOperation(PLUGINS, operation);
            operationIdsByTask.set(operation.acceptedTaskId, operation.operationId);
            const unmatchedTerminal = unmatchedTerminals.get(operation.acceptedTaskId);
            if (unmatchedTerminal) {
                performance.mark(`soai-audit:catalog-consume:${operation.acceptedTaskId}`);
                unmatchedTerminals.delete(operation.acceptedTaskId);
                settleTerminal(unmatchedTerminal.event);
            }
        },
        dispose: (): void => {
            operationIdsByTask.clear();
            unmatchedTerminals.clear();
            unsubscribe();
        }
    });
};

export { createCatalogOptimisticMutations };
export type { CatalogOptimisticMutationDependencies, CatalogOptimisticMutations };
