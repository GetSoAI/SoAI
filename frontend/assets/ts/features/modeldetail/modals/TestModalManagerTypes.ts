/* SoAI - Model test modal manager contracts [frontend/assets/ts/features/modeldetail/modals/TestModalManagerTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/types.ts';

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { CollapseController, CollapseControllerOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';

type TestModalNotificationType = NotificationType;
type TestRunMode = 'short' | 'long';
type TestModalRequestStatus = 'running' | 'success' | 'error' | 'cancelled';

interface TestModalRequestState {
    id: string;
    mode: TestRunMode;
    prompt: string;
    modelId: string;
    modelLabel: string;
    startedAt: number;
    completedAt: number | null;
    status: TestModalRequestStatus;
    response: string;
}

interface TestModalStreamRequestMessage {
    role: 'user' | 'assistant' | 'system' | 'tool';
    content: string;
}

interface TestModalStreamRequest {
    model: string;
    messages: TestModalStreamRequestMessage[];
    stream: true;
}

interface TestModalLogStreamHandlers {
    onOpen?: () => void;
    onClose?: () => void;
    onUpdate?: (data: JsonValue | null | undefined) => void;
    onError?: (error: Error | string | null) => void;
}

interface TestModalLogStreamHandle {
    close: () => void;
}

type TestModalLogEntry = JsonObject;

interface TestModalStatusPresenter {
    allowedColors: string[];
    getDescription: (value: string) => string;
    normalizeStatus: (value: string) => string;
    isError: (value: string) => boolean;
    createStatusBadge: (value: string, description: string) => HTMLElement;
}

interface TestModalModelPort {
    getDocument: () => Document;
    getModel: () => ModelRecord | null;
    readonly modelId: string | null;
    streamLogs: (source: string, handlers: TestModalLogStreamHandlers, options?: JsonObject) => TestModalLogStreamHandle;
    modalPresenter: ModalPresenterApi;
    getPluginStatus: () => string | null;
    getModelDisplayName: () => string;
    getModelSourceModelId: () => string | undefined;
}

interface TestModalViewPort {
    optionalUI: (selector: string | Element, context?: Element) => Element | null;
    showNotification: (message: string, type: TestModalNotificationType) => void;
    sanitizeText: (value: JsonValue | string | null | undefined, options?: { allowEmpty?: boolean }) => string;
    hasClipboardSupport: () => boolean;
    copyToClipboard: (value: string, options?: { notify?: (message: string, type: TestModalNotificationType) => void }) => Promise<void>;
    setTimer: (functionValue: () => void, delay: number, options?: { repeat?: boolean }) => number;
    clearTimer: (timerId: number) => void;
    toggleClassName: (element: Element | null, className: string, force?: boolean) => void;
    addClassName: (element: Element | null, className: string) => void;
    removeClassName: (element: Element | null, className: string) => void;
    updateText: (element: Element | null, text: string) => void;
    updateHTML: (element: Element | null, html: TrustedHtml, options?: { escape?: boolean }) => void;
    updateProperty: (element: Element | null, property: string, value: DomPropertyValue) => void;
}

interface TestModalWorkflowPort {
    statusManager: TestModalStatusPresenter | null;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    createLogsCollapseController: (options: CollapseControllerOptions) => CollapseController;
    getIconSync: (name: string, options?: { size?: number; strokeWidth?: number }) => TrustedHtml;
}

interface TestModalManagerHost {
    model: TestModalModelPort;
    view: TestModalViewPort;
    workflow: TestModalWorkflowPort;
}

interface TestModalState {
    mode: TestRunMode | null;
    active: boolean;
    completed: boolean;
    hasPluginError: boolean;
    errorMessage: string | null;
    logStartedAt: number | null;
    abortController: AbortController | null;
    logEntries: TestModalLogEntry[];
    pendingLogEntries: TestModalLogEntry[];
    logFlushTimerId: number | null;
    logStreamCallback: ((entry: JsonValue | null | undefined) => void) | null;
    logStreamHandle: TestModalLogStreamHandle | null;
    logStreamPluginName: string | null;
    logLineLimit: number;
    elapsedStartTime: number | null;
    elapsedTimerId: number | null;
    currentRequest: TestModalRequestState | null;
    logsCollapseController: CollapseController | null;
}

interface TestModalManagerOptions {
    host: TestModalManagerHost;
}

export type { TestModalLogEntry, TestModalLogStreamHandle, TestModalManagerHost, TestModalManagerOptions, TestModalNotificationType, TestModalRequestState, TestModalRequestStatus, TestRunMode, TestModalState, TestModalStatusPresenter, TestModalStreamRequest };
