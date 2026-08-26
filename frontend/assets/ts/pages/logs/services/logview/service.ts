/* SoAI - Logs page logview service [frontend/assets/ts/pages/logs/services/logview/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { LogStreamView } from '@features/logging/public.ts';
import type { LogEntry } from '@core/logvalidation/types.ts';

interface LogsLogViewHost {
    validateEntry: (entry: JsonValue | LogEntry | null | undefined) => entry is LogEntry;
    getLineLimit: () => number;
    createEntryNode: (entry: LogEntry, sequence: number) => HTMLElement;
    getOutputNode: () => Element | null;
    replaceContent: (output: Element, fragment: DocumentFragment) => void;
    showPlaceholder: (text: string) => void;
    hidePlaceholder: () => void;
    autoScroll: () => boolean;
    scrollToEnd: () => void;
    getPlaceholderText: (status: string) => string;
}

const createLogsLogView = (host: LogsLogViewHost): LogStreamView => {
    return new LogStreamView({
        validateEntry: (entry: JsonValue | LogEntry | null | undefined): entry is LogEntry => host.validateEntry(entry),
        getLineLimit: () => host.getLineLimit(),
        createEntryNode: (entry: LogEntry, sequence: number) => host.createEntryNode(entry, sequence),
        getOutputNode: () => host.getOutputNode(),
        replaceContent: (output: Element, fragment: DocumentFragment) => host.replaceContent(output, fragment),
        removeChild: (node: Node) => removeNodeFromParent(node),
        showPlaceholder: (text: string) => host.showPlaceholder(text),
        hidePlaceholder: () => host.hidePlaceholder(),
        autoScroll: () => host.autoScroll(),
        scrollToEnd: () => host.scrollToEnd(),
        getPlaceholderText: (status: string) => host.getPlaceholderText(status)
    });
};

const removeNodeFromParent = (node: Node): void => {
    const parent = node.parentNode;
    if (parent) {
        parent.removeChild(node);
    }
};

export { createLogsLogView };
export type { LogsLogViewHost };

interface StandardLogsPageHost {
    replaceElementContent: (target: Element, html: DocumentFragment, options?: { escape?: boolean }) => void;
    autoScroll: () => boolean;
    scrollToBottom: () => void;
    getLogLineLimit: () => number;
    validateEntry: (entry: JsonValue | LogEntry | null | undefined) => entry is LogEntry;
    getOutputNode: () => Element | null;
    createEntryNode: (entry: LogEntry, sequence: number) => HTMLElement;
    updatePlaceholder: (text: string) => void;
    hidePlaceholder: () => void;
    getPlaceholderText: (status: string) => string;
}

const createLogsLogViewForStandardPage = (host: StandardLogsPageHost): LogStreamView => {
    return createLogsLogView({
        validateEntry: (entry: JsonValue | LogEntry | null | undefined): entry is LogEntry => host.validateEntry(entry),
        getLineLimit: () => host.getLogLineLimit(),
        createEntryNode: (entry: LogEntry, sequence: number) => host.createEntryNode(entry, sequence),
        getOutputNode: () => host.getOutputNode(),
        replaceContent: (output: Element, fragment: DocumentFragment) => host.replaceElementContent(output, fragment, { escape: false }),
        showPlaceholder: (text: string) => host.updatePlaceholder(text),
        hidePlaceholder: () => host.hidePlaceholder(),
        autoScroll: () => host.autoScroll(),
        scrollToEnd: () => host.scrollToBottom(),
        getPlaceholderText: (status: string) => host.getPlaceholderText(status)
    });
};

export { createLogsLogViewForStandardPage };
export type { StandardLogsPageHost };
