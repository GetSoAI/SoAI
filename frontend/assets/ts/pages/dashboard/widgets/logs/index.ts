/* SoAI - Dashboard page logs entry [frontend/assets/ts/pages/dashboard/widgets/logs/index.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { i18n } from '@core/i18n/index.ts';
import type { LogEntry, ValidationResult } from '@core/logvalidation/types.ts';
import type { LogStreamEvent } from '@features/logging/public.ts';
import { DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE, DASHBOARD_ACTION_LOGS_SIZE_DECREASE, DASHBOARD_ACTION_LOGS_SIZE_INCREASE, type DashboardActionId } from '@pages/dashboard/actions.ts';
import { DashboardLogsStreamController } from '@pages/dashboard/widgets/logs/effects.ts';
import { applyDashboardLogsAction } from '@pages/dashboard/widgets/logs/handlers.ts';
import { DashboardLogsState } from '@pages/dashboard/widgets/logs/state.ts';
import type { DashboardLogsDependencies, DashboardLogsHost, LogValidator } from '@pages/dashboard/widgets/logs/types.ts';
import { DashboardLogsView } from '@pages/dashboard/widgets/logs/view.ts';

class DashboardLogs {
    readonly #host: DashboardLogsHost;
    readonly #validator: LogValidator;
    readonly #state: DashboardLogsState;
    readonly #view: DashboardLogsView;
    readonly #streamController: DashboardLogsStreamController;
    #logView: ReturnType<DashboardLogsView['createLogStreamView']>;

    constructor({ host, validator }: DashboardLogsDependencies) {
        this.#host = host;
        this.#validator = validator;
        this.#state = new DashboardLogsState({ storageGet: this.#host.storageGet, storageSet: this.#host.storageSet });
        this.#view = new DashboardLogsView({
            replaceElementContent: (target: Element, content: string | DocumentFragment | HTMLElement, options?: { escape?: boolean }): void => this.#host.replaceElementContent(target, content, options),
            flushDOMUpdates: (): void => this.#host.flushDOMUpdates(),
            optionalHTMLElement: (selector: string, context?: Element): HTMLElement | null => this.#host.optionalHTMLElement(selector, context),
            updateProperty: (element: Element, property: string, value: DomPropertyValue): void => this.#host.updateProperty(element, property, value),
            updateStyle: (element: Element, property: string, value: string): void => this.#host.updateStyle(element, property, value),
            showNotification: (message, type): void => this.#host.showNotification(message, type)
        });
        this.#logView = this.#createLogStreamView();
        this.#streamController = new DashboardLogsStreamController({
            host: this.#host,
            getReplayLimit: (): number => this.#state.lineLimit,
            onStreamEvent: (event: LogStreamEvent): void => this.#logView.handleStreamEvent({ ...event })
        });
    }

    #createLogStreamView(): ReturnType<DashboardLogsView['createLogStreamView']> {
        return this.#view.createLogStreamView({
            validateEntry: (entry: JsonValue | LogEntry | null | undefined): entry is LogEntry => this.validateEntry(entry),
            getLineLimit: (): number => this.#state.lineLimit,
            createEntryNode: (entry, sequence): HTMLDivElement => this.#view.createEntryNode(entry, sequence),
            getOutputNode: (): Element | null => this.#view.getOutputNode(),
            replaceContent: (target: Element, content: DocumentFragment): void => this.#host.replaceElementContent(target, content, { escape: false }),
            removeChild: (node: Node): void => {
                if (node.parentNode) {
                    node.parentNode.removeChild(node);
                }
            },
            showPlaceholder: (text: string): void => this.#view.renderPlaceholder(text),
            hidePlaceholder: (): void => this.#view.hidePlaceholder(),
            autoScroll: (): boolean => this.#state.autoScroll,
            scrollToEnd: (): void => this.#view.scrollToEnd(),
            getPlaceholderText: (status: string): string | null => this.#view.getPlaceholderText(status)
        });
    }

    mount(content: HTMLElement): void {
        this.#view.mount(content);
        this.#view.applyFontScale(this.#state.fontScale);
        this.#view.renderPlaceholder(i18n.t('dashboard.sections.logs.connecting'));
        if (this.#logView.getEntryCount() > 0) {
            this.render();
        }
    }

    handleAction(actionId: DashboardActionId, target: HTMLElement | null): void {
        if (actionId === DASHBOARD_ACTION_LOGS_SIZE_DECREASE || actionId === DASHBOARD_ACTION_LOGS_SIZE_INCREASE || actionId === DASHBOARD_ACTION_LOGS_AUTOSCROLL_TOGGLE) {
            applyDashboardLogsAction(actionId, target, {
                state: this.#state,
                view: this.#view
            });
        }
    }

    render(): void {
        this.#logView.renderBuffer();
    }

    activate(): Promise<void> {
        return this.#streamController.activate();
    }

    deactivate(): void {
        this.#streamController.deactivate();
    }

    validateEntry(entry: JsonValue | LogEntry | null | undefined): entry is LogEntry {
        if (!entry) {
            this.#host.logError('Invalid log entry: null or undefined');
            return false;
        }
        const validation: ValidationResult = this.#validator.validateLogEntry(entry);
        if (!validation.valid) {
            this.#host.logError(`Invalid log entry: ${validation.errors.join(', ')}`);
            return false;
        }
        return true;
    }

    destroy(): void {
        this.deactivate();
        this.#logView.destroy();
        this.#logView = this.#createLogStreamView();
        this.#view.clearContentNode();
    }
}

export { DashboardLogs };
export type { DashboardLogsHost };
