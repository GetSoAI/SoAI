/* SoAI - Models feature edit model modal contracts [frontend/assets/ts/features/models/modals/editmodelmodal/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { OpenAICapabilityOverrideApi, OpenAICapabilityOverrideCategory } from '@features/models/capabilities/openaiCapabilityState.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';

interface EditModelClipboardApi {
    isSupported(): boolean;
}

interface EditModelViewPort {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    runWithBoundary<T>(operation: string, task: () => Promise<T>): Promise<T>;
    showNotification(message: string, type: NotificationType, duration?: number): void;
    navigateToModelDetail(model: ModelRecord, options?: { tab?: string; action?: string }): void;
    showRenameModelModal(model: ModelRecord): void;
    deleteModel(model: ModelRecord): Promise<void>;
    updateText(element: Element, text: string): void;
    updateHTML(element: Element, html: TrustedHtml | string): void;
    toggleClassName(target: Element, className: string, enabled?: boolean, context?: Element): void;
    setModalBusy(root: HTMLElement, busy: boolean): void;
    resolveModelStatusBadgeClass(model: ModelRecord): string;
    resolveModelStatusLabel(model: ModelRecord): string;
}

interface EditModelOperationsPort {
    getClipboardService(): EditModelClipboardApi;
    copyToClipboard(text: string, options?: { notify?: (message: string, type: NotificationType) => void }): Promise<void>;
    getCapabilityManifest(): JsonObject | null;
    ensureCapabilityManifestReady(): Promise<JsonObject | null>;
    findPluginRecord(pluginName: string): PluginRecord | null;
    resolveOpenAICapabilityLabel(category: OpenAICapabilityOverrideCategory, token: string): string;
    api: OpenAICapabilityOverrideApi & {
        updateEnabled: (modelId: string, payload: { enabled: boolean }) => Promise<SuccessfulMutationResponse>;
    };
    refreshModelsCollection(): Promise<void>;
}

interface EditModelModalHost {
    view: EditModelViewPort;
    operations: EditModelOperationsPort;
}

interface EditModelModalManagerDependencies {
    host: EditModelModalHost;
}

export type { EditModelClipboardApi, EditModelModalHost, EditModelModalManagerDependencies };
