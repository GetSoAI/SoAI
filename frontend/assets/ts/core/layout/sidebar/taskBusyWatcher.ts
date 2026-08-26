/* SoAI - Shared layout task busy watcher [frontend/assets/ts/core/layout/sidebar/taskBusyWatcher.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { SidebarBusyIndicatorRegistry } from '@core/layout/sidebar/busyIndicatorRegistry.ts';
import { SIDEBAR_TASK_BUSY_PAGE_IDS, isTerminalOperationStatus, resolveSidebarTaskBusyPageId, type SidebarTaskBusyPageId } from '@core/layout/sidebar/taskBusyRules.ts';
import { getStreamRuntime } from '@core/realtime/streammanager/public.ts';
import { buildTrackedTaskOperation } from '@core/realtime/streammanager/actions/taskOperations.ts';
import type { OperationEvent } from '@core/realtime/streammanager/types.ts';
import { normalizeWebSocketPayload } from '@core/realtime/streammanager/transport/normalizeWebSocketPayload.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';

const TASK_SOURCE_PREFIX = 'task:';
const TASK_BUSY_RECONCILE_INTERVAL_MS = 15000;

const createTaskSourceMap = (): Map<SidebarTaskBusyPageId, Set<string>> => {
    const sources = new Map<SidebarTaskBusyPageId, Set<string>>();
    for (const pageId of SIDEBAR_TASK_BUSY_PAGE_IDS) {
        sources.set(pageId, new Set<string>());
    }
    return sources;
};

const getTaskSourceSet = (sources: Map<SidebarTaskBusyPageId, Set<string>>, pageId: SidebarTaskBusyPageId): Set<string> => {
    const pageSources = sources.get(pageId);
    if (!pageSources) {
        throw new Error(`Sidebar task busy source set is unavailable for ${pageId}`);
    }
    return pageSources;
};

const buildTaskSourceId = (taskId: string): string => {
    const normalizedTaskId = toTrimmedString(taskId);
    if (!normalizedTaskId) {
        throw new Error('Sidebar task busy source requires a task id');
    }
    return `${TASK_SOURCE_PREFIX}${normalizedTaskId}`;
};

const hasActiveTaskBusyPage = (registry: SidebarBusyIndicatorRegistry): boolean => {
    return SIDEBAR_TASK_BUSY_PAGE_IDS.some((pageId) => registry.hasPageBusy(pageId));
};

const applyTaskSnapshot = (registry: SidebarBusyIndicatorRegistry, snapshotData: JsonValue): void => {
    const normalized = normalizeWebSocketPayload(snapshotData);
    if (!isObject(normalized) || !isArray(normalized['tasks'])) {
        throw new Error('Sidebar task busy snapshot must include tasks array');
    }

    const sources = createTaskSourceMap();
    for (const task of normalized['tasks']) {
        const operation = buildTrackedTaskOperation(task);
        if (!operation) continue;
        const pageId = resolveSidebarTaskBusyPageId(operation.type);
        if (!pageId) continue;
        getTaskSourceSet(sources, pageId).add(buildTaskSourceId(operation.id));
    }

    for (const pageId of SIDEBAR_TASK_BUSY_PAGE_IDS) {
        registry.replacePageSources(pageId, getTaskSourceSet(sources, pageId));
    }
};

const subscribeSidebarTaskBusyWatcher = (registry: SidebarBusyIndicatorRegistry): (() => void) => {
    const streamRuntime = getStreamRuntime();
    let disposed = false;
    let reconciliationTimer: ReturnType<typeof setInterval> | null = null;
    let reconciliationTask: Promise<void> | null = null;

    const stopReconciliationTimer = (): void => {
        if (!reconciliationTimer) return;
        clearInterval(reconciliationTimer);
        reconciliationTimer = null;
    };

    const refreshReconciliationTimer = (): void => {
        if (disposed) return;
        if (!hasActiveTaskBusyPage(registry)) {
            stopReconciliationTimer();
            return;
        }
        if (reconciliationTimer) return;
        reconciliationTimer = setInterval(() => {
            terminateHandledPromise(reconcileFromSnapshot());
        }, TASK_BUSY_RECONCILE_INTERVAL_MS);
    };

    const reconcileFromSnapshot = async (): Promise<void> => {
        if (disposed || reconciliationTask) return reconciliationTask ?? Promise.resolve();
        reconciliationTask = (async (): Promise<void> => {
            try {
                const snapshot = await requestWebSocketSnapshotPayload('tasks.active');
                if (disposed) return;
                applyTaskSnapshot(registry, snapshot);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.debug('Sidebar', 'Task busy snapshot reconciliation failed', runtimeError);
            } finally {
                reconciliationTask = null;
                refreshReconciliationTimer();
            }
        })();
        return reconciliationTask;
    };

    const handleOperation = (event: OperationEvent): void => {
        const sourceId = buildTaskSourceId(event.id);
        if (isTerminalOperationStatus(event.status)) {
            registry.clearSourceFromPages(sourceId, SIDEBAR_TASK_BUSY_PAGE_IDS);
            refreshReconciliationTimer();
            return;
        }

        const pageId = resolveSidebarTaskBusyPageId(event.type);
        if (!pageId) {
            return;
        }
        registry.setBusy(pageId, sourceId, true);
        refreshReconciliationTimer();
    };

    const unsubscribeOperations = streamRuntime.tasks.subscribeOperations(handleOperation);
    const unsubscribeConnected = subscribeManagedWebSocketContract({
        label: 'SidebarTaskBusyWatcher',
        contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
        handler: () => {
            terminateHandledPromise(reconcileFromSnapshot());
        }
    });
    terminateHandledPromise(
        streamRuntime.resources.ensureReady({ allowDiscovery: true, throwOnError: false }).then(() => {
            terminateHandledPromise(streamRuntime.tasks.reconnectOperations());
            terminateHandledPromise(reconcileFromSnapshot());
        })
    );

    return () => {
        disposed = true;
        stopReconciliationTimer();
        unsubscribeOperations();
        unsubscribeConnected();
        for (const pageId of SIDEBAR_TASK_BUSY_PAGE_IDS) {
            registry.replacePageSources(pageId, new Set<string>());
        }
    };
};

export { applyTaskSnapshot, subscribeSidebarTaskBusyWatcher };
