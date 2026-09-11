/* SoAI - Logs page mappers [frontend/assets/ts/pages/logs/mappers/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { requireDocument } from '@core/environment/public.ts';
import { formatUtcLogTimestamp } from '@core/localization/public.ts';
import type { LogEntry } from '@core/logvalidation/types.ts';
import { normalizeLogMessage, setLogEntryClipboardText } from '@features/logging/public.ts';

const buildLogMessageContent = (entry: LogEntry): Text => {
    const normalized = normalizeLogMessage(entry);
    return requireDocument().createTextNode(normalized);
};

const buildLogEntryNode = (entry: LogEntry, sequence: number): HTMLElement => {
    const doc = requireDocument();
    const line = doc.createElement('div');
    line.className = 'log-entry';
    const level = String(entry['level'] || 'INFO').toUpperCase();
    line.dataset['level'] = level;
    line.dataset['component'] = String(entry['component'] ?? '');
    setLogEntryClipboardText(line, entry);

    const timestamp = doc.createElement('span');
    timestamp.className = 'log-timestamp';
    timestamp.textContent = formatUtcLogTimestamp(String(entry['timestamp'] ?? ''));

    const component = doc.createElement('span');
    component.className = 'log-component';
    component.textContent = String(entry['component'] ?? '');

    const levelSpan = doc.createElement('span');
    levelSpan.className = 'log-level';
    levelSpan.dataset['level'] = level;
    levelSpan.textContent = level;

    const message = doc.createElement('span');
    const checkerboard = resolveCheckerboardClass(sequence);
    message.className = `log-message ${checkerboard}`;
    message.appendChild(buildLogMessageContent(entry));

    line.append(timestamp, component, levelSpan, message);
    return line;
};

export { buildLogEntryNode };
