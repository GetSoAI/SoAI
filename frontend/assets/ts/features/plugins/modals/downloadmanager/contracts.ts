/* SoAI - Plugins feature download manager contracts [frontend/assets/ts/features/plugins/modals/downloadmanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { OperationProgressData } from '@core/operationprogress/types.ts';
import type { StreamTaskRuntimeContract } from '@core/realtime/streammanager/actions/contracts.ts';
import type { StreamActionHandle, StreamHandleTrackerContract } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { RequiredClassNames } from '@core/ui/classNames.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { DisableControlHost } from '@features/plugins/contracts/pluginPageSupport.ts';
import type { ManualInstallPathResponse } from '@core/api/contracts/manualInstallPathContracts.ts';

interface StreamHandlerCallbacks {
    onProgress?(data: JsonValue | null | undefined): void;
}

interface OperationMeta extends JsonObject {
    type: string;
    pluginName: string;
    url: string;
    source: string;
}

type AcceptedTaskTrackingOptions = NonNullable<Parameters<StreamTaskRuntimeContract['trackAcceptedTask']>[1]> & {
    handlers: StreamActionHandlers;
    operation: OperationMeta;
};

interface ProgressReporter {
    update(key: string, data: OperationProgressData): void;
    remove(key: string): void;
    clear(): void;
    destroy(): void;
    hasActiveOperations(): boolean;
}

interface DownloadApiInterface {
    uploadFile(url: string, file: File, additionalData?: Record<string, string | Blob>, options?: RequestOptions, filenameOverride?: string | null): Promise<ApiResponsePayload>;
    plugins: { manualInstall(): Promise<ManualInstallPathResponse> };
}

interface ManualPluginState {
    loading: boolean;
    loaded: boolean;
    promise: Promise<ManualPluginState | null> | null;
    pluginsPath: string;
    resolvedPath: string;
    error: Error | null;
}

interface ClipboardNotifyOptions {
    notify(message: string, type: string): void;
}

interface PluginDownloadViewPort extends DisableControlHost {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    updateText(target: Element | string, text: string): void;
    updateHTML(target: Element | string, html: TrustedHtml | string): void;
    addClassName(target: Element | string, classes: string | string[]): void;
    removeClassName(target: Element | string, classes: string | string[]): void;
    setUIValue(target: string | Element, value: JsonValue | null | undefined, options?: { attribute?: string }): void;
    updateProperty(target: Element | string, property: string, value: DomPropertyValue): void;
    updateAttribute(target: Element | string, attribute: string, value: string | null): void;
    toggleClassName(target: Element | string, className: string, force?: boolean | null): void;
}

interface PluginDownloadExecutionPort {
    streams: StreamHandleTrackerContract;
    cancelDownload(key: string): void;
    createStreamHandlers(key: string, message: string, callbacks: StreamHandlerCallbacks): StreamActionHandlers;
    trackAcceptedTask(taskId: Parameters<StreamTaskRuntimeContract['trackAcceptedTask']>[0], options: AcceptedTaskTrackingOptions): ReturnType<StreamTaskRuntimeContract['trackAcceptedTask']>;
    startTaskAction(
        url: string,
        options: {
            method: string;
            body: JsonValue | null | undefined;
            handlers: StreamActionHandlers;
            operation: OperationMeta;
        }
    ): Promise<StreamActionHandle>;
    api: DownloadApiInterface;
    createOperationProgressReporter(
        containerId: string,
        options: {
            onCancel?: (key: string) => void;
            backgroundButtonId?: string;
        }
    ): ProgressReporter | null | undefined;
}

interface PluginDownloadSessionPort {
    hasClipboardSupport(): boolean;
    copyToClipboard(value: string, options?: ClipboardNotifyOptions): Promise<void>;
    showNotification(message: string, type?: NotificationType, duration?: number): void;
    sanitizeHtml(value: string): string;
    isAdmin(): boolean;
    setLocationHash(hash: string): void;
}

interface DownloadManagerHost {
    view: PluginDownloadViewPort;
    execution: PluginDownloadExecutionPort;
    session: PluginDownloadSessionPort;
}

interface DownloadManagerOptions {
    host: DownloadManagerHost;
    classNames: RequiredClassNames;
}

export type { StreamHandlerCallbacks, OperationMeta, ProgressReporter, DownloadApiInterface, ManualPluginState, ClipboardNotifyOptions };
export type { DownloadManagerHost, DownloadManagerOptions };
