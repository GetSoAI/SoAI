/* SoAI - Dashboard page logs rendering [frontend/assets/ts/pages/dashboard/widgets/logs/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { requireDocument } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { LogEntry } from '@core/logvalidation/types.ts';
import { bindLogSelectionCopy, LogStreamView, normalizeLogMessage, setLogEntryClipboardText } from '@features/logging/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface DashboardLogsViewHost {
    replaceElementContent: (target: Element, content: string | DocumentFragment | HTMLElement, options?: { escape?: boolean }) => void;
    flushDOMUpdates(): void;
    optionalHTMLElement(selector: string, context?: Element | null): HTMLElement | null;
    updateProperty(element: Element, property: string, value: DomPropertyValue): void;
    updateStyle(element: Element, property: string, value: string): void;
    showNotification(message: string, type: NotificationType): void;
}

interface DashboardLogsStreamViewDependencies {
    validateEntry(entry: JsonValue | LogEntry | null | undefined): entry is LogEntry;
    getLineLimit(): number;
    createEntryNode(entry: LogEntry, sequence: number): HTMLDivElement;
    getOutputNode(): Element | null;
    replaceContent(target: Element, content: DocumentFragment): void;
    removeChild(node: Node): void;
    showPlaceholder(text: string): void;
    hidePlaceholder(): void;
    autoScroll(): boolean;
    scrollToEnd(): void;
    getPlaceholderText(status: string): string | null;
}

class DashboardLogsView {
    readonly #host: DashboardLogsViewHost;
    #contentNode: HTMLElement | null = null;
    #copyAbortController: AbortController | null = null;

    constructor(host: DashboardLogsViewHost) {
        this.#host = host;
    }

    mount(content: HTMLElement): void {
        this.#contentNode = content;
        this.#host.updateProperty(content, 'className', 'section-content logs-viewer');
        const doc = requireDocument();
        const logsContent = doc.createElement('div');
        logsContent.className = 'logs-content';
        logsContent.id = 'log-content-area';
        content.replaceChildren(logsContent);
        this.#copyAbortController?.abort();
        this.#copyAbortController = new AbortController();
        bindLogSelectionCopy({ root: logsContent, signal: this.#copyAbortController.signal, showNotification: (message, type) => this.#host.showNotification(message, type) });
        this.#host.flushDOMUpdates();
    }

    clearContentNode(): void {
        this.#copyAbortController?.abort();
        this.#copyAbortController = null;
        this.#contentNode = null;
    }

    getPlaceholderText(status: string): string | null {
        if (status === 'reconnecting') {
            return i18n.t('dashboard.sections.logs.reconnecting');
        }
        if (status === 'connecting') {
            return i18n.t('dashboard.sections.logs.connecting');
        }
        return null;
    }

    renderPlaceholder(text: string): void {
        const output = this.getOutputNode();
        if (!output) {
            return;
        }
        const doc = requireDocument();
        const placeholder = doc.createElement('div');
        placeholder.className = 'log-entry';
        placeholder.dataset['level'] = 'INFO';
        placeholder.dataset['placeholder'] = 'true';
        placeholder.textContent = text;
        output.replaceChildren(placeholder);
    }

    hidePlaceholder(): void {
        const output = this.getOutputNode();
        if (!output) {
            return;
        }
        const placeholder = this.#host.optionalHTMLElement('[data-placeholder="true"]', output);
        if (placeholder) {
            placeholder.remove();
        }
    }

    createEntryNode(entry: LogEntry, index: number): HTMLDivElement {
        const doc: Document = requireDocument();
        const line: HTMLDivElement = doc.createElement('div');
        line.className = 'log-entry';
        line.dataset['level'] = entry['level'];
        line.dataset['component'] = entry['component'] ?? '';
        setLogEntryClipboardText(line, entry);
        const timestamp = doc.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = entry['timestamp'];
        const component = doc.createElement('span');
        component.className = 'log-component';
        component.textContent = entry['component'] ?? '';
        const level = doc.createElement('span');
        level.className = 'log-level';
        level.dataset['level'] = entry['level'];
        level.textContent = entry['level'];
        const message = doc.createElement('span');
        const checkerboard = resolveCheckerboardClass(index);
        message.className = `log-message ${checkerboard}`;
        message.append(this.buildMessageContent(entry));
        line.append(timestamp, component, level, message);
        return line;
    }

    getOutputNode(): HTMLElement | null {
        const byId = this.#host.optionalHTMLElement('#log-content-area');
        if (byId instanceof HTMLElement) {
            return byId;
        }
        if (!this.#contentNode) {
            return null;
        }
        return this.#host.optionalHTMLElement('.logs-content', this.#contentNode);
    }

    applyFontScale(fontScale: number): void {
        const output = this.getOutputNode();
        if (output) {
            this.#host.updateStyle(output, 'fontSize', `${fontScale}rem`);
        }
    }

    scrollToEnd(): void {
        const output = this.getOutputNode();
        if (output) {
            this.#host.updateProperty(output, 'scrollTop', output.scrollHeight);
        }
    }

    buildMessageContent(entry: LogEntry): Text {
        const normalized = normalizeLogMessage(entry);
        return requireDocument().createTextNode(normalized);
    }

    createLogStreamView(dependencies: DashboardLogsStreamViewDependencies): LogStreamView {
        return new LogStreamView({
            validateEntry: dependencies.validateEntry,
            getLineLimit: dependencies.getLineLimit,
            createEntryNode: dependencies.createEntryNode,
            getOutputNode: dependencies.getOutputNode,
            replaceContent: dependencies.replaceContent,
            removeChild: dependencies.removeChild,
            showPlaceholder: dependencies.showPlaceholder,
            hidePlaceholder: dependencies.hidePlaceholder,
            autoScroll: dependencies.autoScroll,
            scrollToEnd: dependencies.scrollToEnd,
            getPlaceholderText: dependencies.getPlaceholderText
        });
    }
}

export { DashboardLogsView };
