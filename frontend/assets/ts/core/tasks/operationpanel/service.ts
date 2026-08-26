/* SoAI - Shared tasks operation panel service [frontend/assets/ts/core/tasks/operationpanel/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createOperationProgressReporter } from '@core/operationprogress/public.ts';
import type { OperationProgressReporter } from '@core/operationprogress/types.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveTaskProgressState, type TaskProgressState } from '@core/tasks/operationPayloads.ts';
import { normalizeProgress } from '@core/primitives/progress.ts';
import { resolveTaskOperationDetailText, resolveTaskOperationLabelText } from '@core/tasks/operationText.ts';
import { resolveTaskOperationPluginName } from '@core/tasks/operationPlugin.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { TaskOperationEntry, TaskOperationFilter, TaskOperationsApi } from '@core/tasks/protocols.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface TaskOperationPanelOptions {
    container: string | HTMLElement;
    filter: TaskOperationFilter;
    operationsApi?: TaskOperationsApi | undefined;
    showCancel?: boolean | undefined;
    backgroundButtonId?: string | undefined;
    normalizeProgress?: ((value: JsonValue | null | undefined) => number) | undefined;
}

const buildQueuedBadgeMap = (operations: TaskOperationEntry[]): Map<string, string> => {
    const seenPluginNames = new Set<string>();
    const queuedBadges = new Map<string, string>();
    for (const operation of operations) {
        if (operation.type !== 'model-download') {
            continue;
        }
        const pluginName = resolveTaskOperationPluginName(operation);
        if (!pluginName) {
            continue;
        }
        const pluginKey = pluginName.toLowerCase();
        if (seenPluginNames.has(pluginKey)) {
            queuedBadges.set(operation.id, i18n.t('taskManager.badges.queuedForPlugin', { plugin: pluginName }));
            continue;
        }
        seenPluginNames.add(pluginKey);
    }
    return queuedBadges;
};

class TaskOperationPanel {
    readonly #container: string | HTMLElement;
    readonly #filter: TaskOperationFilter;
    readonly #operationsApi: TaskOperationsApi;
    readonly #normalizeProgress: (value: JsonValue | null | undefined) => number;
    readonly #showCancel: boolean;
    readonly #backgroundButtonId: string | null;
    #reporter: OperationProgressReporter | null = null;
    #unsubscribe: (() => void) | null = null;
    readonly #renderedOperationIds = new Set<string>();

    constructor(options: TaskOperationPanelOptions) {
        this.#container = options.container;
        this.#filter = options.filter;
        this.#operationsApi = options.operationsApi ?? requireTaskOperationsApi();
        this.#normalizeProgress = options.normalizeProgress ?? ((value) => normalizeProgress(value) ?? 0);
        this.#showCancel = options.showCancel !== false;
        this.#backgroundButtonId = options.backgroundButtonId ?? null;
    }

    attach(): void {
        this.detach();
        this.#reporter = createOperationProgressReporter(this.#container, {
            showCancel: this.#showCancel,
            backgroundButtonId: this.#backgroundButtonId,
            onCancel: (operationId: string): Promise<void> => this.#cancelOperation(operationId)
        });
        this.#unsubscribe = this.#operationsApi.subscribeOperations(this.#filter, (operations) => {
            this.#render(operations);
        });
    }

    detach(): void {
        const unsubscribe = this.#unsubscribe;
        this.#unsubscribe = null;
        runCleanup(unsubscribe, (runtimeError) => {
            errorHandler.warn('TaskOperationPanel', 'Operation subscription cleanup failed', runtimeError);
        });
        this.#reporter?.destroy();
        this.#reporter = null;
        this.#renderedOperationIds.clear();
    }

    refreshFilter(filter: TaskOperationFilter): void {
        this.#filter.types = filter.types;
        this.#filter.pluginKey = filter.pluginKey;
        this.#filter.pluginName = filter.pluginName;
        this.#filter.conversationId = filter.conversationId;
        if (this.#reporter) {
            this.#render(this.#operationsApi.getOperations(this.#filter));
        }
    }

    #render(operations: TaskOperationEntry[]): void {
        const reporter = this.#reporter;
        if (!reporter) {
            return;
        }
        const nextOperationIds = new Set<string>();
        const queuedBadges = buildQueuedBadgeMap(operations);
        for (const operation of operations) {
            nextOperationIds.add(operation.id);
            const progress = this.#normalizeProgress(operation.progress);
            const label = resolveTaskOperationLabelText(operation);
            const details = resolveTaskOperationDetailText(operation);
            const badge = queuedBadges.get(operation.id) ?? '';
            const state = badge ? 'pending' : this.#resolveProgressState(operation);
            reporter.update(operation.id, {
                progress,
                message: label,
                badge,
                details,
                state,
                cancelable: operation.cancelable === true
            });
        }
        for (const operationId of this.#renderedOperationIds) {
            if (!nextOperationIds.has(operationId)) {
                reporter.remove(operationId);
            }
        }
        this.#renderedOperationIds.clear();
        for (const operationId of nextOperationIds) {
            this.#renderedOperationIds.add(operationId);
        }
    }

    #resolveProgressState(operation: TaskOperationEntry): TaskProgressState {
        const meta = operation.meta;
        const taskStatus = meta?.['taskStatus'];
        return resolveTaskProgressState(isString(taskStatus) ? taskStatus : undefined);
    }

    async #cancelOperation(operationId: string): Promise<void> {
        await this.#operationsApi.cancelOperationById(operationId);
    }
}

const createTaskOperationPanel = (options: TaskOperationPanelOptions): TaskOperationPanel => new TaskOperationPanel(options);

export { TaskOperationPanel, createTaskOperationPanel };
export type { TaskOperationPanelOptions };
