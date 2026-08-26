/* SoAI - Logs output view, validation, placeholder, scrolling, and line-limit ownership [frontend/assets/ts/pages/logs/controllers/page/LogsViewSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LogEntry } from '@core/logvalidation/types.ts';
import { getLogValidation } from '@core/logvalidation/public.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { LogStreamView } from '@features/logging/public.ts';
import { DEFAULT_LOG_LINE_LIMIT } from '@pages/logs/contracts/constants.ts';
import { clearLogsPage } from '@pages/logs/controllers/page/logsPageClearController.ts';
import { hideLogsPlaceholder, resolveLogsPlaceholderText, showLogsPlaceholder } from '@pages/logs/controllers/page/logsPagePlaceholderController.ts';
import { isLogsAtBottom, scrollLogsToBottom } from '@pages/logs/controllers/page/logsPageScrollController.ts';
import { requireLogsUi } from '@pages/logs/dom.ts';
import { buildLogEntryNode } from '@pages/logs/mappers/mappers.ts';
import { createLogsLogViewForStandardPage } from '@pages/logs/services/logview/service.ts';
import type { LogsUiRefs, StreamPayload } from '@pages/logs/types.ts';

const LOGS_BOTTOM_LOCK_THRESHOLD_PX = 2;

class LogsViewSession {
    autoScroll = true;
    lineLimit = DEFAULT_LOG_LINE_LIMIT;
    readonly #pageDom: PageDom;
    readonly #storage: StorageService;
    readonly #document: Document;
    readonly #view: LogStreamView;
    #ui: LogsUiRefs | null = null;

    constructor(dependencies: { document: Document; pageDom: PageDom; storage: StorageService }) {
        this.#document = dependencies.document;
        this.#pageDom = dependencies.pageDom;
        this.#storage = dependencies.storage;
        this.#view = createLogsLogViewForStandardPage({
            replaceElementContent: (target, html, options) => this.#pageDom.replaceContent(target, html, options),
            autoScroll: () => this.autoScroll,
            scrollToBottom: () => this.#scrollToBottom(),
            getLogLineLimit: () => this.lineLimit,
            validateEntry: (entry): entry is LogEntry => this.#validateEntry(entry),
            getOutputNode: () => this.output,
            createEntryNode: buildLogEntryNode,
            updatePlaceholder: (text) => this.#updatePlaceholder(text),
            hidePlaceholder: () => this.#hidePlaceholder(),
            getPlaceholderText: (status) => resolveLogsPlaceholderText(status)
        });
    }

    get ui(): LogsUiRefs {
        if (this.#ui) return this.#ui;
        this.#ui = requireLogsUi({
            requireHTMLElement: (selector, context) => this.#pageDom.requireHTMLElement(selector, context),
            optionalHTMLElement: (selector, context) => this.#pageDom.optionalHTMLElement(selector, context)
        });
        return this.#ui;
    }

    get output(): Element | null {
        return this.#ui?.output ?? null;
    }

    initialize(): void {
        void this.ui;
    }

    handlePayload(payload: StreamPayload): void {
        this.#view.handleStreamEvent({ ...payload });
    }

    renderBuffer(): void {
        this.#view.renderBuffer();
    }

    readonly handleScroll = (): void => {
        this.autoScroll = isLogsAtBottom(this.ui.root, LOGS_BOTTOM_LOCK_THRESHOLD_PX);
    };

    clear(): void {
        clearLogsPage({
            doc: this.#document,
            ui: this.ui,
            output: this.output,
            logView: this.#view,
            replaceElementContent: (target, html, options) => this.#pageDom.replaceContent(target, html, options)
        });
    }

    updateLineLimit(limit: number): boolean {
        const validation = getLogValidation().validateLogLineLimit(limit);
        if (!validation.valid || validation.limit === null) return false;
        this.lineLimit = validation.limit;
        this.#storage.setLogLineLimit?.(validation.limit);
        this.#view.applyLineLimit();
        return true;
    }

    resetForSourceChange(connectingText: string): void {
        this.#view.reset();
        if (this.output) this.#pageDom.replaceContent(this.output, this.#document.createDocumentFragment(), { escape: false });
        this.#updatePlaceholder(connectingText);
    }

    destroy(): void {
        this.#view.destroy();
        this.#ui = null;
    }

    #validateEntry(entry: JsonValue | LogEntry | null | undefined): entry is LogEntry {
        return Boolean(entry) && getLogValidation().validateLogEntry(entry).valid;
    }

    #updatePlaceholder(text: string): void {
        showLogsPlaceholder(this.ui, text);
    }

    #hidePlaceholder(): void {
        hideLogsPlaceholder(this.ui);
    }

    #scrollToBottom(): void {
        this.#pageDom.flush();
        scrollLogsToBottom(this.ui.root);
    }
}

export { LogsViewSession };
