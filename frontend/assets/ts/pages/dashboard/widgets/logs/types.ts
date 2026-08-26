/* SoAI - Dashboard page logs contracts [frontend/assets/ts/pages/dashboard/widgets/logs/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { LogEntry, ValidationResult } from '@core/logvalidation/types.ts';
import type { LogStreamEvent } from '@features/logging/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

type DashboardLogStreamHandler = (event: LogStreamEvent) => void;

interface DashboardLogStream {
    subscribe(handler: DashboardLogStreamHandler, options?: { replayLimit?: number; source?: string }): () => void;
}

interface DashboardLogsHost {
    storageGet: (key: string, defaultValue?: JsonValue) => JsonValue;
    storageSet: (key: string, value: JsonValue) => void;
    replaceElementContent(target: Element, content: string | DocumentFragment | HTMLElement, options?: { escape?: boolean }): void;
    flushDOMUpdates(): void;
    optionalHTMLElement(selector: string, context?: Element | null): HTMLElement | null;
    updateProperty(element: Element, property: string, value: DomPropertyValue): void;
    updateHTML(element: Element, html: string): void;
    updateStyle(element: Element, property: string, value: string): void;
    ensureLogStreamReady(): Promise<DashboardLogStream>;
    logError(message: string, detail?: JsonValue | Error | null): void;
    isDestroyed(): boolean;
    showNotification(message: string, type: NotificationType): void;
}

interface LogValidator {
    validateLogEntry(entry: JsonValue | LogEntry | null | undefined): ValidationResult;
}

interface DashboardLogsLineLimitStorage {
    storageGet: (key: string, defaultValue?: JsonValue) => JsonValue;
    storageSet: (key: string, value: JsonValue) => void;
}

interface DashboardLogsDependencies {
    host: DashboardLogsHost;
    validator: LogValidator;
}

export type { DashboardLogStream, DashboardLogStreamHandler, DashboardLogsHost, DashboardLogsDependencies, DashboardLogsLineLimitStorage, LogValidator };
