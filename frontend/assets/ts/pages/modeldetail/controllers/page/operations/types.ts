/* SoAI - Model detail page control layer operations public contracts [frontend/assets/ts/pages/modeldetail/controllers/page/operations/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { ElementOptions } from '@core/dom/types.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/stream/types.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { StreamHandle } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';

interface ModelDetailOperationsHost extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    activeDeletionStream: StreamHandle | null;
    model: ModelRecord | null;
    modelId: string | null;
    ensureUi: () => {
        deleteModelButton: HTMLElement;
    };
    getElement: (selector: string, context?: Element) => Element | null;
    dom: {
        create: (tagName: string, options?: ElementOptions) => HTMLElement;
    };
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    runPageTask: (taskKey: string, task: () => Promise<JsonValue>, options: { displayName: string; rethrow: boolean }) => Promise<JsonValue>;
    startTaskAction: (
        endpoint: string,
        options: {
            method: string;
            handlers?: Record<string, (payload: JsonValue) => void>;
            operation?: Record<string, JsonValue>;
        }
    ) => Promise<StreamActionHandle>;
    getStreamTracker: (key: string) => {
        track: (id: string, handle: StreamHandle) => void;
        release: (id: string) => void;
    };
    getModelDisplayName: () => string;
    getPluginStatus: () => string | null;
    requireModelId: () => string;
    isVirtualModel: () => boolean;
    api: {
        routing: {
            virtualModels: {
                delete: (modelName: string) => Promise<SuccessfulMutationResponse>;
            };
        };
    };
    router: {
        navigate: (page: string) => void;
    };
}

interface ModelDetailOperationsDependencies extends PageStreamingOwnerHost, PageUiOwnerHost, PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost, PageLifecycleOwnerHost {
    session: ModelDetailSession;
    ensureUi: () => { deleteModelButton: HTMLElement };
    dom: ModelDetailOperationsHost['dom'];
    requireModelId: ModelDetailOperationsHost['requireModelId'];
    isVirtualModel: ModelDetailOperationsHost['isVirtualModel'];
    api: ModelDetailOperationsHost['api'];
    router: { navigate: (page: string) => void } | null;
}

export type { ModelDetailOperationsDependencies, ModelDetailOperationsHost };
