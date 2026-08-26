/* SoAI - Logging feature log stream view [frontend/assets/ts/features/logging/LogStreamView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { dom } from '@core/dom/dom.ts';
import type { LogEntry } from '@core/logvalidation/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { normalizeLogMessage } from '@features/logging/logMessage.ts';

interface TrackedEntry {
    entry: LogEntry;
    sequence: number;
}

interface LogStreamConfig {
    getPlaceholderText(status: string): string | null;
    showPlaceholder(text: string): void;
    hidePlaceholder(): void;
    validateEntry(entry: JsonValue | LogEntry | null | undefined): entry is LogEntry;
    isDuplicate?(lastEntry: LogEntry | null, nextEntry: LogEntry): boolean;
    getOutputNode(): Element | null;
    createEntryNode(entry: LogEntry, sequence: number): Node;
    replaceContent(output: Element, fragment: DocumentFragment): void;
    autoScroll(): boolean;
    scrollToEnd(): void;
    getLineLimit(): number;
    removeChild?(node: Node): void;
}

class LogStreamView {
    config: LogStreamConfig;
    entries: TrackedEntry[] = [];
    sequence: number = 0;
    historyPending: boolean = false;
    #renderQueue: AnimationFrameRenderQueue<boolean>;
    #destroyed: boolean = false;
    #lastRenderSignature: string | null = null;
    #renderedFirstSequence: number | null = null;
    #renderedLastSequence: number | null = null;

    constructor(config: LogStreamConfig) {
        this.config = config;
        this.entries = [];
        this.sequence = 0;
        this.historyPending = false;
        this.#renderQueue = new AnimationFrameRenderQueue({
            label: 'LogStreamView',
            render: () => this.#renderBuffer(),
            merge: () => true,
            isDisposed: () => this.#destroyed
        });
        this.#destroyed = false;
    }

    #resolveEntriesSignature(): string {
        const entriesSignature = this.entries
            .map((trackedEntry) => {
                const entry = trackedEntry.entry;
                return [this.#signaturePart(String(trackedEntry.sequence)), this.#signaturePart(entry.timestamp), this.#signaturePart(entry.level), this.#signaturePart(entry.component), this.#signaturePart(normalizeLogMessage(entry))].join('');
            })
            .join('');
        return `${this.#signaturePart(String(this.config.getLineLimit()))}${this.#signaturePart(String(this.entries.length))}${entriesSignature}`;
    }

    #signaturePart(value: string): string {
        return `${String(value.length)}:${value}`;
    }

    handleStreamEvent(event: JsonValue | null | undefined): void {
        if (!event || !isObject(event)) return;
        const typeValue = event['type'];
        if (!isString(typeValue)) return;
        if (typeValue === 'connection') {
            const statusValue = event['status'];
            const status = isString(statusValue) ? statusValue : 'connecting';
            this.handleConnection(status);
            return;
        }
        if (typeValue === 'snapshot') {
            this.historyPending = false;
            this.queueRender();
            return;
        }
        if (typeValue === 'history') {
            const entriesValue = event['entries'];
            if (!isArray(entriesValue)) {
                return;
            }
            this.replaceHistory(entriesValue);
            return;
        }
        if (typeValue === 'log') {
            const modeValue = event['mode'];
            const mode = isString(modeValue) ? modeValue : null;
            const buffered = mode === 'replay' || mode === 'history';
            if (buffered) {
                this.historyPending = true;
                if (this.appendEntry(event['entry'])) {
                    this.queueRender();
                }
                return;
            }
            if (this.historyPending) {
                this.historyPending = false;
                this.queueRender();
            }
            if (this.appendEntry(event['entry'])) {
                this.queueRender();
            }
        }
    }

    handleConnection(status: string): void {
        if (this.entries.length) {
            return;
        }
        const placeholder = this.config.getPlaceholderText(status);
        if (placeholder) {
            this.config.showPlaceholder(placeholder);
        }
    }

    appendEntry(entry: JsonValue | LogEntry | null | undefined): boolean {
        if (!this.config.validateEntry(entry)) {
            return false;
        }
        const validatedEntry: LogEntry = entry;
        const last = this.entries[this.entries.length - 1];
        if (this.isDuplicate(last, validatedEntry)) {
            return false;
        }
        const trackedEntry: TrackedEntry = { entry: validatedEntry, sequence: this.sequence++ };
        this.entries.push(trackedEntry);
        this.trimEntries();
        return true;
    }

    replaceHistory(entries: ReadonlyArray<JsonValue | LogEntry | null | undefined>): void {
        this.entries = [];
        this.sequence = 0;
        entries.forEach((entry) => {
            if (!this.config.validateEntry(entry)) {
                return;
            }
            const validatedEntry: LogEntry = entry;
            this.entries.push({ entry: validatedEntry, sequence: this.sequence++ });
        });
        this.trimEntries();
        this.historyPending = false;
        this.#renderedFirstSequence = null;
        this.#renderedLastSequence = null;
        this.queueRender();
    }

    isDuplicate(lastEntry: TrackedEntry | undefined, nextEntry: LogEntry): boolean {
        if (typeof this.config.isDuplicate === 'function') {
            return this.config.isDuplicate(lastEntry?.entry ?? null, nextEntry);
        }
        return normalizeLogMessage(lastEntry?.entry ?? null) === normalizeLogMessage(nextEntry);
    }

    removeChild(node: Node): void {
        if (this.config.removeChild) {
            this.config.removeChild(node);
            return;
        }
        node.parentNode?.removeChild(node);
    }

    trimEntries(): void {
        if (!Array.isArray(this.entries)) {
            this.reset();
            return;
        }
        const limit = this.config.getLineLimit();
        if (!Number.isFinite(limit) || limit <= 0) {
            this.reset();
            return;
        }
        if (this.entries.length <= limit) {
            return;
        }
        const overflow = this.entries.length - limit;
        this.entries.splice(0, overflow);
    }

    queueRender(): void {
        this.#renderQueue.schedule(true);
    }

    renderBuffer(): void {
        this.#renderBuffer();
    }

    #renderBuffer(): void {
        if (this.#destroyed) {
            return;
        }
        const output = this.config.getOutputNode();
        if (!output) {
            return;
        }
        const renderSignature = this.#resolveEntriesSignature();
        if (this.#lastRenderSignature === renderSignature) {
            return;
        }
        if (!this.entries.length) {
            const emptyFragment = dom.createFragment();
            this.config.replaceContent(output, emptyFragment);
            this.#lastRenderSignature = renderSignature;
            this.#renderedFirstSequence = null;
            this.#renderedLastSequence = null;
            const placeholder = this.config.getPlaceholderText('connecting');
            if (placeholder) {
                this.config.showPlaceholder(placeholder);
            }
            return;
        }
        this.config.hidePlaceholder();
        const firstEntry = this.entries[0];
        const lastEntry = this.entries[this.entries.length - 1];
        if (!firstEntry || !lastEntry) {
            return;
        }
        const firstSequence = firstEntry.sequence;
        const lastSequence = lastEntry.sequence;
        const previousFirstSequence = this.#renderedFirstSequence;
        const previousLastSequence = this.#renderedLastSequence;
        if (previousFirstSequence !== null && previousLastSequence !== null) {
            this.#reconcileIncrementally(output, firstSequence, lastSequence, previousFirstSequence, previousLastSequence);
        } else {
            this.#replaceAllRenderedEntries(output);
        }
        this.#renderedFirstSequence = firstSequence;
        this.#renderedLastSequence = lastSequence;
        this.#lastRenderSignature = renderSignature;
        if (this.config.autoScroll()) {
            this.config.scrollToEnd();
        }
    }

    #reconcileIncrementally(output: Element, firstSequence: number, lastSequence: number, previousFirstSequence: number, previousLastSequence: number): void {
        const removedCount = firstSequence - previousFirstSequence;
        for (let index = 0; index < removedCount; index += 1) {
            if (!output.firstChild) {
                break;
            }
            this.removeChild(output.firstChild);
        }
        const newCount = lastSequence - previousLastSequence;
        if (newCount <= 0) {
            return;
        }
        const newEntries = this.entries.slice(this.entries.length - newCount);
        const fragment = dom.createFragment();
        newEntries.forEach((trackedEntry) => {
            fragment.appendChild(this.config.createEntryNode(trackedEntry.entry, trackedEntry.sequence));
        });
        output.appendChild(fragment);
    }

    #replaceAllRenderedEntries(output: Element): void {
        const fragment = dom.createFragment();
        this.entries.forEach((trackedEntry) => {
            fragment.appendChild(this.config.createEntryNode(trackedEntry.entry, trackedEntry.sequence));
        });
        this.config.replaceContent(output, fragment);
    }

    applyLineLimit(): void {
        this.trimEntries();
        this.#renderBuffer();
    }

    reset(): void {
        this.entries = [];
        this.sequence = 0;
        this.#lastRenderSignature = null;
        this.#renderedFirstSequence = null;
        this.#renderedLastSequence = null;
    }

    showPlaceholder(text: string): void {
        if (text) {
            this.config.showPlaceholder(text);
        }
    }

    destroy(): void {
        this.#destroyed = true;
        this.#renderQueue.dispose();
        this.reset();
    }

    getEntryCount(): number {
        return this.entries.length;
    }
}

export { LogStreamView };
export type { TrackedEntry, LogStreamConfig };
