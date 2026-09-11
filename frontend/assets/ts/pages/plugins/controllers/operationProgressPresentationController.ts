/* SoAI - Plugins operation progress presentation [frontend/assets/ts/pages/plugins/controllers/operationProgressPresentationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';
import { PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_UPDATING } from '@core/state/pluginStatus.ts';
import { matches } from '@core/dom/dom.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { clearProgressUsageClass, syncDeterminateProgress } from '@core/ui/progressWidths.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import { resolveTaskOperationTypeLabelText } from '@core/tasks/operationText.ts';

const STATUS_LINE_SELECTOR = '.ui-collection-card__status-line';
const CARD_PROGRESS_CLASS = 'ui-collection-card__status-line--progress';
const STATUS_BADGE_SELECTOR = '.ui-metric-badge--status-full';
const BACKEND_BADGE_SELECTOR = '.ui-metric-badge--secondary[data-metric-key="backend"]';
const CARD_ACTIVE_OPERATION_ATTRIBUTE = 'data-operation-active';
const METRIC_VALUE_SELECTOR = '.ui-metric-value';
const METRIC_PROGRESS_ATTRIBUTE = 'data-progress';
const STATUS_BADGE_CLASS_PREFIX = 'ui-metric-badge--status-';
const CARD_PROGRESS_STYLE_PROPERTY = '--ui-collection-card-progress';

interface PluginOperationProjection {
    type: string;
    progress: number;
}

interface ElementPresentation {
    className: string;
    status: string | null;
    value: string;
}

interface PluginOperationPresentationDependencies extends PageDomOwnerHost {
    getStatusManager(): StatusManager;
}

class PluginOperationProgressPresentationController {
    readonly #dependencies: PluginOperationPresentationDependencies;
    readonly #statusBadgePresentations = new WeakMap<HTMLElement, ElementPresentation>();
    readonly #backendBadgePresentations = new WeakMap<HTMLElement, ElementPresentation>();
    readonly #listStatusPresentations = new WeakMap<HTMLElement, ElementPresentation>();

    constructor(dependencies: PluginOperationPresentationDependencies) {
        this.#dependencies = dependencies;
    }

    apply(items: Iterable<HTMLElement>, operations: ReadonlyMap<string, PluginOperationProjection>, activePluginKeys: ReadonlySet<string>, getPluginKey: (source: string | null | undefined) => string | null): void {
        for (const item of items) {
            const pluginKey = getPluginKey(item.dataset['plugin']);
            const operation = pluginKey ? operations.get(pluginKey) : undefined;
            const hasActiveOperation = pluginKey ? activePluginKeys.has(pluginKey) : false;
            this.#dependencies.pageDom.updateAttribute(item, CARD_ACTIVE_OPERATION_ATTRIBUTE, hasActiveOperation || operation ? 'true' : null);
            if (matches(item, '.plugins-list-row')) this.#applyList(item, operation);
            else this.#applyCard(item, operation);
        }
    }

    #applyCard(card: HTMLElement, operation: PluginOperationProjection | undefined): void {
        const statusLine = this.#requireOne(STATUS_LINE_SELECTOR, card, 'grid card status line');
        if (!operation) {
            this.#clearCardProgress(statusLine);
            this.#restoreOperationBadges(card);
            return;
        }
        this.#syncCardProgress(statusLine, operation.progress);
        this.#applyOperationBadges(card, operation);
    }

    #applyList(row: HTMLElement, operation: PluginOperationProjection | undefined): void {
        const cell = this.#requireOne('.plugins-list-status', row, 'list status cell');
        const status = this.#requireOne('.ui-collection-list__status', cell, 'list status presentation');
        const label = this.#requireOne(':scope > span:not(.status-led)', status, 'list status label');
        if (!operation) {
            const presentation = this.#listStatusPresentations.get(status);
            if (presentation) {
                this.#dependencies.pageDom.updateAttribute(status, 'class', presentation.className);
                this.#dependencies.pageDom.updateText(label, presentation.value);
                this.#listStatusPresentations.delete(status);
            }
            return;
        }
        if (!this.#listStatusPresentations.has(status)) this.#listStatusPresentations.set(status, { className: status.className, status: null, value: label.textContent ?? '' });
        const transientStatus = operation.type === 'backend-install' ? PLUGIN_STATUS_BACKEND_INSTALLING : operation.type === 'backend-update' ? PLUGIN_STATUS_BACKEND_UPDATING : null;
        const operationLabel = transientStatus ? this.#applyTransientListStatus(status, transientStatus) : this.#restoreListStatusClass(status, operation.type);
        this.#dependencies.pageDom.updateText(label, `${operationLabel} · ${formatPercent(operation.progress, 0)}`);
    }

    #restoreListStatusClass(status: HTMLElement, operationType: string): string {
        const presentation = this.#listStatusPresentations.get(status);
        if (!presentation) throw new Error('Plugins list operation presentation is missing its underlying status');
        this.#dependencies.pageDom.updateAttribute(status, 'class', presentation.className);
        return resolveTaskOperationTypeLabelText(operationType);
    }

    #applyTransientListStatus(status: HTMLElement, transientStatus: string): string {
        const statusManager = this.#dependencies.getStatusManager();
        this.#dependencies.pageDom.updateAttribute(status, 'class', `ui-collection-list__status ${statusManager.getCollectionBadgeClass(transientStatus)}`);
        return statusManager.getDescription(transientStatus);
    }

    #syncCardProgress(element: HTMLElement, progress: number): void {
        this.#dependencies.pageDom.addClass(element, CARD_PROGRESS_CLASS);
        this.#dependencies.pageDom.updateAttribute(element, 'role', 'progressbar');
        this.#dependencies.pageDom.updateAttribute(element, 'aria-valuemin', '0');
        this.#dependencies.pageDom.updateAttribute(element, 'aria-valuemax', '100');
        syncDeterminateProgress({
            fillElement: element,
            progress,
            progressbarElement: element,
            syncUsageClass: true,
            setStyle: (target, _property, value) => this.#dependencies.pageDom.updateStyle(target, CARD_PROGRESS_STYLE_PROPERTY, value),
            setAttribute: (target, name, value) => this.#dependencies.pageDom.updateAttribute(target, name, value)
        });
    }

    #clearCardProgress(element: HTMLElement): void {
        if (!element.classList.contains(CARD_PROGRESS_CLASS)) return;
        this.#dependencies.pageDom.removeClass(element, CARD_PROGRESS_CLASS);
        clearProgressUsageClass(element);
        this.#dependencies.pageDom.updateStyle(element, CARD_PROGRESS_STYLE_PROPERTY, null);
        for (const name of ['role', 'aria-valuemin', 'aria-valuemax', 'aria-valuenow']) this.#dependencies.pageDom.updateAttribute(element, name, null);
    }

    #requireOne(selector: string, context: HTMLElement, label: string): HTMLElement {
        const elements = this.#dependencies.pageDom.query(selector, context);
        const element = elements[0];
        if (elements.length !== 1 || !(element instanceof HTMLElement)) throw new TypeError(`Plugins operation presentation requires exactly one HTMLElement ${label}`);
        return element;
    }

    #captureBadge(badge: HTMLElement, presentations: WeakMap<HTMLElement, ElementPresentation>): HTMLElement {
        const value = this.#requireOne(METRIC_VALUE_SELECTOR, badge, 'metric value');
        if (!presentations.has(badge)) presentations.set(badge, { className: badge.className, status: badge.getAttribute('data-status'), value: value.textContent ?? '' });
        return value;
    }

    #applyOperationBadges(card: HTMLElement, operation: PluginOperationProjection): void {
        const transientStatus = operation.type === 'backend-install' ? PLUGIN_STATUS_BACKEND_INSTALLING : operation.type === 'backend-update' ? PLUGIN_STATUS_BACKEND_UPDATING : null;
        const progressLabel = formatPercent(operation.progress, 0);
        if (!transientStatus) {
            this.#restoreOperationBadges(card);
            const statusBadge = this.#requireOne(STATUS_BADGE_SELECTOR, card, 'status badge');
            const statusValue = this.#requireOne(METRIC_VALUE_SELECTOR, statusBadge, 'metric value');
            this.#dependencies.pageDom.updateAttribute(statusValue, METRIC_PROGRESS_ATTRIBUTE, progressLabel);
            return;
        }
        const statusManager = this.#dependencies.getStatusManager();
        const statusLabel = statusManager.getDescription(transientStatus);
        const backendLabel = transientStatus === PLUGIN_STATUS_BACKEND_INSTALLING ? i18n.t('plugins.status.installing') : i18n.t('plugins.status.updating');
        const statusBadge = this.#requireOne(STATUS_BADGE_SELECTOR, card, 'status badge');
        const statusValue = this.#captureBadge(statusBadge, this.#statusBadgePresentations);
        this.#dependencies.pageDom.updateAttribute(statusValue, METRIC_PROGRESS_ATTRIBUTE, progressLabel);
        const classes = Array.from(statusBadge.classList).filter((className) => className === 'ui-metric-badge--status-full' || !className.startsWith(STATUS_BADGE_CLASS_PREFIX));
        classes.push(`ui-metric-badge--${statusManager.getCollectionBadgeClass(transientStatus)}`);
        this.#dependencies.pageDom.updateAttribute(statusBadge, 'class', classes.join(' '));
        this.#dependencies.pageDom.updateAttribute(statusBadge, 'data-status', transientStatus);
        this.#dependencies.pageDom.updateText(statusValue, statusLabel);
        const backendBadge = this.#requireOne(BACKEND_BADGE_SELECTOR, card, 'backend badge');
        const backendValue = this.#captureBadge(backendBadge, this.#backendBadgePresentations);
        this.#dependencies.pageDom.updateAttribute(backendBadge, 'data-status', transientStatus);
        this.#dependencies.pageDom.updateText(backendValue, backendLabel);
    }

    #restoreBadge(badge: HTMLElement, presentations: WeakMap<HTMLElement, ElementPresentation>): void {
        const presentation = presentations.get(badge);
        if (!presentation) return;
        const value = this.#requireOne(METRIC_VALUE_SELECTOR, badge, 'metric value');
        this.#dependencies.pageDom.updateAttribute(badge, 'class', presentation.className);
        this.#dependencies.pageDom.updateAttribute(badge, 'data-status', presentation.status);
        this.#dependencies.pageDom.updateText(value, presentation.value);
        presentations.delete(badge);
    }

    #restoreOperationBadges(card: HTMLElement): void {
        const statusBadge = this.#dependencies.pageDom.optionalHTMLElement(STATUS_BADGE_SELECTOR, card);
        if (statusBadge) {
            this.#restoreBadge(statusBadge, this.#statusBadgePresentations);
            const statusValue = this.#requireOne(METRIC_VALUE_SELECTOR, statusBadge, 'metric value');
            this.#dependencies.pageDom.updateAttribute(statusValue, METRIC_PROGRESS_ATTRIBUTE, null);
        }
        const backendBadge = this.#dependencies.pageDom.optionalHTMLElement(BACKEND_BADGE_SELECTOR, card);
        if (backendBadge) this.#restoreBadge(backendBadge, this.#backendBadgePresentations);
    }
}

export { PluginOperationProgressPresentationController };
export type { PluginOperationPresentationDependencies, PluginOperationProjection };
