/* SoAI - Tasks feature task manager view [frontend/assets/ts/features/tasks/taskmanager/TaskManagerView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { reconcileElementChildrenFromTrustedHtml } from '@core/dom/childNodeReconciliation.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireHeaderDropdownButton, requireHeaderDropdownElement } from '@core/layout/header/dropdownElements.ts';
import { securityApi, toTrustedUiHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { syncTrackedTaskCounter } from '@core/tasks/taskCounterText.ts';
import { resolveTaskOperationDetailText, resolveTaskOperationLabelText } from '@core/tasks/operationText.ts';
import { isHTMLElement, isObject, isString } from '@core/typeGuards.ts';
import { readRequiredTrimmedStringMessageValue } from '@core/types/payloadValueReaders.ts';
import { DROPDOWN_CHEVRON_OPTIONS } from '@core/ui/dropdown/chevron.ts';
import { getIcon, getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setIconSlot } from '@core/ui/icons/view.ts';
import { syncDeterminateProgress } from '@core/ui/progressWidths.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { PluginEntry } from '@features/tasks/taskmanager/taskManagerModels.ts';
import { buildOperationSignature, renderOperationRow, resolveOperationContext } from '@features/tasks/taskmanager/service.ts';
import type { TaskManagerElements, TaskManagerStoreApi } from '@features/tasks/taskmanager/taskManagerTypes.ts';

interface StatusManagerContract {
    createIndicator: (status: string) => HTMLElement;
}

class TaskManagerView {
    #store: TaskManagerStoreApi;
    #statusManager: StatusManagerContract;
    #stopIconMarkup: ReturnType<typeof getIconSync> | null = null;
    #listStructureSignature: string | null = null;

    constructor(options: { store: TaskManagerStoreApi; statusManager: StatusManagerContract }) {
        this.#store = options.store;
        this.#statusManager = options.statusManager;
    }

    reset(): void {
        this.#stopIconMarkup = null;
        this.#listStructureSignature = null;
    }

    resolveElements(): TaskManagerElements {
        return {
            manager: requireHeaderDropdownElement('#header-task-manager', 'task manager container'),
            toggle: requireHeaderDropdownElement('.header-task-manager-toggle', 'toggle container'),
            panel: requireHeaderDropdownElement('#header-task-list-panel', 'task list panel'),
            list: requireHeaderDropdownElement('#task-list', 'task list'),
            stopAllButton: requireHeaderDropdownButton('.stop-all-tasks', 'stop-all'),
            title: requireHeaderDropdownElement('.header-task-manager-title', 'task title')
        };
    }

    async setupIcons(elements: TaskManagerElements): Promise<void> {
        const iconElement = dom.resolve('.stop-icon', elements.stopAllButton);
        if (!isHTMLElement(iconElement)) {
            throw new Error('TaskManager stop-all button must contain .stop-icon element');
        }
        const markup = await getIcon('stop', { size: 18, strokeWidth: 1.5 });
        setIconSlot(iconElement, markup, { className: iconElement.className });

        const chevronElement = dom.resolve('.tasks-chevron', elements.toggle);
        if (!isHTMLElement(chevronElement)) {
            throw new Error('TaskManager toggle must contain .tasks-chevron element');
        }
        const chevronMarkup = await getIcon('chevron-down', DROPDOWN_CHEVRON_OPTIONS);
        setIconSlot(chevronElement, chevronMarkup, { className: chevronElement.className });
    }

    applyLocalization(elements: TaskManagerElements, isExpanded: boolean): void {
        const toggleLabel = i18n.t('taskManager.actions.togglePanel');
        dom.setAttribute(elements.toggle, 'role', 'button');
        dom.setAttribute(elements.toggle, 'tabindex', '0');
        dom.setAttribute(elements.toggle, 'aria-controls', elements.panel.id);
        dom.setAttribute(elements.toggle, 'aria-label', toggleLabel);
        setTooltipText(elements.toggle, toggleLabel);
        const stopAllLabel = i18n.t('taskManager.actions.stopAll');
        dom.setAttribute(elements.stopAllButton, 'aria-label', stopAllLabel);
        setTooltipText(elements.stopAllButton, stopAllLabel);
        dom.setAttribute(elements.manager, 'aria-label', i18n.t('taskManager.aria.panel'));
        this.setExpandedState(elements, isExpanded);
        this.updateHeader(elements);
    }

    updateHeader(elements: TaskManagerElements): void {
        const taskCount = this.#store.getActivePluginCount();
        const headerLabel = dom.resolve('.header-task-manager-label', elements.toggle);
        syncTrackedTaskCounter(taskCount, elements.manager.ownerDocument, headerLabel);
        const hasTasks = taskCount > 0;
        const hasStopActions = this.#store.getStoppableCount() > 0 || this.#store.getCancelableOperations().length > 0;
        elements.stopAllButton.toggleAttribute('hidden', !hasStopActions);

        if (hasTasks) {
            dom.setText(elements.title, i18n.t('taskManager.header.titleWithCount', { count: taskCount }));
        } else {
            dom.setText(elements.title, i18n.t('taskManager.actions.togglePanel'));
        }
    }

    setExpandedState(elements: TaskManagerElements, isExpanded: boolean): void {
        dom.setAttribute(elements.toggle, 'aria-expanded', isExpanded ? 'true' : 'false');
        dom.toggleClass(elements.manager, 'header-task-manager--expanded', isExpanded);
        dom.setAttribute(elements.panel, 'aria-hidden', isExpanded ? 'false' : 'true');
    }

    renderPluginList(elements: TaskManagerElements): void {
        this.updateHeader(elements);
        const pluginEntries: PluginEntry[] = [...this.#store.getActivePlugins()];
        const seenKeys = new Set(
            pluginEntries
                .map((point) => {
                    const key = this.#store.getPluginKey(point);
                    if (!key) {
                        throw new Error('TaskManager plugin entry missing plugin key');
                    }
                    return key;
                })
                .filter((key) => key)
        );
        this.#store.getActiveOperations().forEach((op) => {
            if (!op || !isObject(op)) {
                throw new Error('TaskManager encountered invalid operation record');
            }
            const pluginKey = op.pluginKey;
            if (!isString(pluginKey) || !pluginKey.trim()) {
                throw new Error('TaskManager operation missing pluginKey');
            }
            if (seenKeys.has(pluginKey)) {
                return;
            }
            const context = resolveOperationContext(op);
            pluginEntries.push({ name: context.name, state: 'PROCESSING', __synthetic: true, __pluginKey: pluginKey });
            seenKeys.add(pluginKey);
        });
        const filteredEntries = pluginEntries;
        const operationLabelDependencies = {
            store: this.#store
        };
        if (filteredEntries.length === 0) {
            reconcileElementChildrenFromTrustedHtml({ target: elements.list, html: uiHtml`<div class="task-list-empty"><p>${i18n.t('taskManager.messages.noActivePlugins')}</p></div>` });
            this.#listStructureSignature = null;
            return;
        }
        const structureSignature = filteredEntries
            .map((plugin) => {
                const pluginName = this.#store.resolvePluginDisplayName(plugin);
                const pluginKey = this.#store.getPluginKey(plugin);
                if (!pluginKey) {
                    throw new Error('TaskManager plugin signature requires plugin key');
                }
                const status = String(plugin.state ?? 'UNKNOWN').toUpperCase();
                const isSynthetic = plugin.__synthetic === true;
                const displayStatus = isSynthetic ? 'PROCESSING' : status;
                const ops = this.#store.getOperationsForPlugin(plugin);
                const opsSignature = ops
                    .map((op) => buildOperationSignature(op))
                    .sort((left, right) => left.localeCompare(right, 'en'))
                    .join(',');
                return `${pluginKey}|${pluginName}|${displayStatus}|${isSynthetic ? '1' : '0'}|${opsSignature}`;
            })
            .sort((left, right) => left.localeCompare(right, 'en'))
            .join(';;');
        if (this.#listStructureSignature === structureSignature && elements.list.childElementCount > 0) {
            const rowsByOperation = new Map<string, HTMLElement>();
            for (const element of dom.resolveAll('.task-operation-row--inline[data-operation]', elements.list)) {
                if (!isHTMLElement(element)) continue;
                const opId = element.dataset['operation']?.trim();
                if (opId) rowsByOperation.set(opId, element);
            }
            let requiresFullRender = false;
            const operations = this.#store.getActiveOperations();
            for (const op of operations) {
                const opId = readRequiredTrimmedStringMessageValue(op.id, 'TaskManager operation requires an identifier for in-place update');
                const row = rowsByOperation.get(opId) || null;
                if (!row) {
                    requiresFullRender = true;
                    break;
                }
                const percent = this.#store.normalizeProgress(op.progress);
                const progressContainer = dom.resolve('.task-progress[role="progressbar"]', row);
                const progressBar = dom.resolve('.task-progress-bar--determinate', row);
                const labelElement = dom.resolve('.task-operation-label', row);
                const detailElement = dom.resolve('.task-operation-detail', row);
                if (!(progressContainer instanceof HTMLElement) || !(progressBar instanceof HTMLElement)) {
                    requiresFullRender = true;
                    break;
                }
                if (!(labelElement instanceof HTMLElement) || !(detailElement instanceof HTMLElement)) {
                    requiresFullRender = true;
                    break;
                }
                const normalizedProgress = syncDeterminateProgress({
                    fillElement: progressBar,
                    progress: percent,
                    progressbarElement: progressContainer,
                    syncUsageClass: true
                });
                progressBar.dataset['progress'] = String(normalizedProgress);
                dom.setText(labelElement, resolveTaskOperationLabelText(op));
                dom.setText(detailElement, resolveTaskOperationDetailText(op));
            }
            if (!requiresFullRender) {
                return;
            }
        }
        const listHTML = filteredEntries
            .map((plugin, index) => {
                const pluginName = this.#store.resolvePluginDisplayName(plugin);
                const pluginKey = this.#store.getPluginKey(plugin);
                if (!pluginKey) {
                    throw new Error('TaskManager plugin rendering requires plugin key');
                }
                const checkerboardClass = resolveCheckerboardClass(index);
                const status = String(plugin.state ?? 'UNKNOWN').toUpperCase();
                const isSynthetic = plugin.__synthetic === true;
                const isPersistent = this.#store.isPersistentStatus(status);
                const displayStatus = isSynthetic ? 'PROCESSING' : status;
                const indicatorNode = this.#statusManager.createIndicator(displayStatus);
                const indicatorMarkup = serializeElementToHtml(indicatorNode);
                if (!indicatorMarkup) {
                    throw new Error(`Status manager failed to render indicator for ${displayStatus}`);
                }
                const ops = this.#store.getOperationsForPlugin(plugin);
                const hasOps = ops.length > 0;
                const hasCancel = ops.some((op) => op.cancelable);
                const hasRealTask = ops.some((op) => {
                    const meta = isObject(op.meta) ? op.meta : {};
                    return isString(meta.taskId) && meta.taskId.trim();
                });
                const shouldCancelOperation = isSynthetic && hasCancel && hasRealTask;
                const canStopPlugin = !isPersistent && !shouldCancelOperation;
                const pluginActionName = (isString(plugin.name) && plugin.name.trim()) || (isString(plugin.identifier) && plugin.identifier.trim()) || (isString(plugin.plugin) && plugin.plugin.trim()) || pluginName;
                const stopBtnTitle = shouldCancelOperation ? i18n.t('taskManager.actions.cancelOperation') : i18n.t('taskManager.actions.stopPlugin', { pluginName: pluginName });
                const stopBtn =
                    shouldCancelOperation || canStopPlugin
                        ? `
                <button type="button" class="task-stop-btn"
                data-plugin="${securityApi.escapeHtml(pluginActionName)}"
                data-plugin-key="${pluginKey ? securityApi.escapeHtml(pluginKey) : ''}"
                data-synthetic="${isSynthetic}"
                data-has-operations="${hasOps}"
                data-can-cancel="${shouldCancelOperation}"
                data-tooltip="${securityApi.escapeHtml(stopBtnTitle)}"
                aria-label="${securityApi.escapeHtml(stopBtnTitle)}">
                ${this.#getStopIconMarkup().html}
                </button>
                `
                        : '';
                return `
            <div class="dropdown-item task-item ${checkerboardClass}" data-plugin="${securityApi.escapeHtml(pluginName)}">
            <div class="active-task-info">
            <div class="plugin-status">${indicatorMarkup}</div>
            <div class="active-task-details">
            <div class="active-task-name">
            <span class="task-name-text">${securityApi.escapeHtml(pluginName)}</span>
            </div>
            ${hasOps ? ops.map((op) => renderOperationRow(op, operationLabelDependencies)).join('') : ''}
            </div>
            </div>
            ${stopBtn}
                 </div>`;
            })
            .join('');
        const listMarkup = toTrustedUiHtml(listHTML);
        dom.setHTML(elements.list, listMarkup, { escape: false });
        this.#listStructureSignature = structureSignature;
        for (const bar of dom.resolveAll('.task-progress-bar--determinate[data-progress]', elements.list)) {
            if (!isHTMLElement(bar)) continue;
            const value = Number(bar.dataset['progress']);
            if (Number.isFinite(value)) {
                syncDeterminateProgress({
                    fillElement: bar,
                    progress: value,
                    syncUsageClass: true
                });
            }
        }
    }

    #getStopIconMarkup(): ReturnType<typeof getIconSync> {
        if (this.#stopIconMarkup && this.#stopIconMarkup.html.trim()) {
            return this.#stopIconMarkup;
        }
        const markup = getIconSync('stop', { size: 14, strokeWidth: 1.5 });
        this.#stopIconMarkup = markup;
        return markup;
    }
}
export { TaskManagerView };
