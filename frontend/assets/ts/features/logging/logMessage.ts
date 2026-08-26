/* SoAI - Logging feature log message [frontend/assets/ts/features/logging/logMessage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined, isString } from '@core/typeGuards.ts';

interface LogEntry {
    message?: string | undefined;
    text?: string | undefined;
}

const normalizeLogMessage = (entry: LogEntry | null | undefined): string => {
    const raw = isString(entry?.message) && entry.message.length > 0 ? entry.message : (entry?.text ?? '');
    if (isNullOrUndefined(raw)) {
        return '';
    }
    return String(raw);
};

export { normalizeLogMessage };
export type { LogEntry };
