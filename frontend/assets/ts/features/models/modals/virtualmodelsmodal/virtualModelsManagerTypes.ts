/* SoAI - Virtual model manager host and state contracts [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StreamSubscriptions } from '@core/realtime/streammanager/streamSubscriptions.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { VirtualModelStrategy } from '@core/storage/types.ts';
import type { ModelsCollectionView } from '@features/models/modals/virtualmodelsmodal/virtualmodelsmanager/contracts.ts';
import type { VirtualModelCreateRequest, VirtualModelResponse, VirtualModelUpdateRequest } from '@core/api/contracts/virtualModelContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';

interface VirtualModelsViewPort {
    modals: ModalPresenterApi;
    requireUI(selector: string | Element, context?: Element): Element;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    queryUI(selector: string | Element | string[], context?: Element): Element[];
    showNotification(message: string, type?: NotificationType, duration?: number): void;
    dom: {
        getData(target: Element, name: string): string | null;
        setData(target: Element, name: string, value: string): void;
    };
    sanitizer: Pick<SanitizerApi, 'attribute' | 'html'>;
    setUIValue(target: string | Element, value: JsonValue | null | undefined, options?: { attribute?: string }): void;
    updateHTML(target: Element | string, html: TrustedHtml | string): void;
    updateText(target: Element | string, text: string): void;
    toggleClassName(target: Element | string | null, className: string, force?: boolean | null): void;
    addClassName(target: Element | string | null, classes: string | string[]): void;
}

interface VirtualModelsDataPort {
    api: {
        routing: {
            virtualModels: {
                get(name: string): Promise<VirtualModelResponse>;
                create(payload: VirtualModelCreateRequest): Promise<SuccessfulMutationResponse>;
                update(name: string, payload: VirtualModelUpdateRequest): Promise<SuccessfulMutationResponse>;
                delete(name: string): Promise<SuccessfulMutationResponse>;
            };
        };
    };
    getCollection(): ModelsCollectionView | null;
    requireStreamSubscriptions(): StreamSubscriptions;
    on(target: EventTarget | Element, event: string, handler: EventListener, options?: AddEventListenerOptions): () => void;
    removeItemById(identifier: string, options?: { emit?: boolean }): void;
    getItemCardId(item: JsonValue | null | undefined): string;
}

interface VirtualModelsPreferencePort {
    formatStrategyLabel(strategy: JsonValue | null | undefined): string;
    getLastVirtualModelStrategy(): VirtualModelStrategy;
    setLastVirtualModelStrategy(value: VirtualModelStrategy): void;
}

export interface VirtualModelsHost {
    view: VirtualModelsViewPort;
    data: VirtualModelsDataPort;
    preferences: VirtualModelsPreferencePort;
}

export interface VirtualModelsManagerDependencies {
    host: VirtualModelsHost;
}

export interface VirtualModelRecord {
    name: string;
    strategy: string;
    models: ModelEntry[];
}

export interface ModelEntry {
    universalId: string;
}

export type VirtualModelsPrimaryTab = 'create' | 'list';

export interface VirtualModelState {
    virtualModelCount: number;
    virtualModelCache: VirtualModelRecord[];
    subscription: { unsubscribe: () => void } | null;
    activeTab: VirtualModelsPrimaryTab;
    editModalOpen: boolean;
    directEditSession: boolean;
    originalCreateName: string;
    originalCreateStrategy: string;
    originalCreateModels: string[];
    originalEditStrategy: string;
    originalEditModels: string[];
}
