/* SoAI - Plugins feature clone contracts [frontend/assets/ts/features/plugins/modals/clone/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { OperationProgressData } from '@core/operationprogress/types.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { BaseClassNames } from '@core/ui/classNames.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface SecurityService {
    escapeHtml(value: string): string;
}

interface CloneProgressReporter {
    update(key: string, data: OperationProgressData): void;
    remove(key: string): void;
    clear(): void;
    destroy(): void;
    hasActiveOperations(): boolean;
}

interface CloneOptions {
    cloneModels?: boolean;
    targetName?: string | null;
}

interface CloneState {
    currentCloningPlugin: PluginRecord | null;
}

interface CloneOperationMeta {
    type: string;
    pluginName: string;
    plugin: string;
    displayName: string;
    message: string;
    cancelable: boolean;
    operationKey: string;
    requestId: string;
}

interface CloneTaskActionOptions {
    method: string;
    body: JsonValue | null | undefined;
    handlers: StreamActionHandlers;
    operation: CloneOperationMeta;
}

interface CloneStatusPresenter {
    getDescription(status: string): string;
    updateIndicator(element: HTMLElement | null, status: string): void;
}

interface CloneManagerStreams {
    track(key: string, stream: StreamActionHandle): void;
    release(key: string): void;
}

interface CloneModalViewPort {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    updateText(target: Element | string, text: string): void;
    updateHTML(target: Element | string, html: TrustedHtml | string): void;
    addClassName(target: Element | string, classes: string | string[]): void;
    toggleClassName(target: Element | string, className: string, force?: boolean | null): void;
    updateProperty(target: Element | string, property: string, value: DomPropertyValue): void;
    on(element: Element, event: string, handler: (event: Event) => void): () => void;
}

interface ClonePluginPolicyPort {
    formatPluginName(name: string): string;
    getPluginStatus(plugin: PluginRecord): string;
    sanitizeText(value: JsonValue | null | undefined, options?: Record<string, JsonValue | null | undefined>): string;
    statusManager: CloneStatusPresenter;
    isPluginIncompatible(plugin: PluginRecord): boolean;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    showNotification(message: string, type?: NotificationType, duration?: number): void;
}

interface CloneExecutionPort {
    setPluginProgressMeta(key: string, meta: Record<string, JsonValue | null | undefined>): void;
    createStreamHandlers: (
        key: string,
        message: string,
        callbacks?: {
            onProgress?: (data: JsonValue | null | undefined) => void;
            onComplete?: (data: JsonValue | null | undefined) => void;
            onError?: (error: Error) => void;
        }
    ) => StreamActionHandlers;
    startTaskAction: (url: string, options: CloneTaskActionOptions) => Promise<StreamActionHandle>;
    streams: CloneManagerStreams;
    consumePluginProgressMeta(key: string): Record<string, JsonValue | null | undefined> | null;
    createOperationProgressReporter(container: string, options: { onCancel?: (key: string) => void; backgroundButtonId?: string; cancelSelector?: string | null; showCancel?: boolean }): CloneProgressReporter | null;
}

interface CloneManagerHost {
    view: CloneModalViewPort;
    policy: ClonePluginPolicyPort;
    execution: CloneExecutionPort;
}

interface CloneManagerOptions {
    host: CloneManagerHost;
    classNames: BaseClassNames;
    security: SecurityService;
}

interface CloneActionContext {
    host: CloneManagerHost;
    plugin: PluginRecord;
    cloneOptions: CloneOptions;
    modalId: string;
    startButton: HTMLButtonElement;
    setCloneControlDisabled: (element: Element, disabled: boolean) => void;
    requireCloneProgressReporter: () => CloneProgressReporter;
}

export type { CloneActionContext, CloneManagerHost, CloneManagerOptions, CloneOptions, CloneProgressReporter, CloneState, SecurityService };
