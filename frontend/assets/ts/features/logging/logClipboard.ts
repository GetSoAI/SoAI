/* SoAI - Logging feature log clipboard [frontend/assets/ts/features/logging/logClipboard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LogEntry } from '@core/logvalidation/types.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatUtcLogTimestamp } from '@core/localization/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { normalizeLogMessage } from '@features/logging/logMessage.ts';

const LOG_COPY_ROW_SELECTOR = '[data-log-copy-text]';
const ANSI_ESCAPE_PATTERN = new RegExp(`${String.fromCharCode(27)}\\[[0-?]*[ -/]*[@-~]`, 'g');
const CLIPBOARD_FIELD_SEPARATOR_PATTERN = /[\t\r\n]+/g;

interface LogSelectionCopyBinding {
    root: Element;
    signal: AbortSignal;
    showNotification: (message: string, type: NotificationType) => void;
}

const formatLogEntryForClipboard = (entry: LogEntry): string => {
    return [formatUtcLogTimestamp(entry.timestamp), entry.component, entry.level, normalizeClipboardLogMessage(entry)].map((field) => normalizeClipboardField(field)).join('\t');
};

const normalizeClipboardLogMessage = (entry: LogEntry): string => {
    return normalizeLogMessage(entry).replace(ANSI_ESCAPE_PATTERN, '');
};

const normalizeClipboardField = (value: string): string => {
    return value.replace(CLIPBOARD_FIELD_SEPARATOR_PATTERN, ' ');
};

const setLogEntryClipboardText = (element: HTMLElement, entry: LogEntry): void => {
    element.dataset['logCopyText'] = formatLogEntryForClipboard(entry);
};

const readLogEntryClipboardText = (element: HTMLElement): string | null => {
    const value = element.dataset['logCopyText'];
    return typeof value === 'string' && value.length > 0 ? value : null;
};

const resolveSelectedLogRows = (root: Element, selection: Selection): HTMLElement[] => {
    const selectedRows: HTMLElement[] = [];
    const candidates = dom.resolveAll(LOG_COPY_ROW_SELECTOR, root);
    for (const candidate of candidates) {
        if (!(candidate instanceof HTMLElement)) {
            continue;
        }
        for (let rangeIndex = 0; rangeIndex < selection.rangeCount; rangeIndex += 1) {
            if (selection.getRangeAt(rangeIndex).intersectsNode(candidate)) {
                selectedRows.push(candidate);
                break;
            }
        }
    }
    return selectedRows;
};

const resolveSelectedLogClipboardText = (root: Element, selection: Selection | null): string | null => {
    if (!selection || selection.isCollapsed || selection.rangeCount <= 0) {
        return null;
    }
    const lines: string[] = [];
    for (const row of resolveSelectedLogRows(root, selection)) {
        const line = readLogEntryClipboardText(row);
        if (line) {
            lines.push(line);
        }
    }
    return lines.length > 0 ? lines.join('\n') : null;
};

const bindLogSelectionCopy = ({ root, signal, showNotification }: LogSelectionCopyBinding): void => {
    const doc = root.ownerDocument;
    doc.addEventListener(
        'copy',
        (event: ClipboardEvent): void => {
            const text = resolveSelectedLogClipboardText(root, doc.getSelection());
            if (!text || !event.clipboardData) {
                return;
            }
            event.clipboardData.setData('text/plain', text);
            event.preventDefault();
            showNotification(i18n.t('common.clipboard.copied'), 'copy');
        },
        { signal }
    );
};

export { bindLogSelectionCopy, formatLogEntryForClipboard, resolveSelectedLogClipboardText, setLogEntryClipboardText };
