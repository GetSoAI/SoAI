/* SoAI - Model detail session state [frontend/assets/ts/pages/modeldetail/state/ModelDetailSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ParametersData, StreamHandle, StreamSubscription } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { ModelDetailUi } from '@pages/modeldetail/dom.ts';

class ModelDetailSession {
    realtimeCollectionsInitialized = false;
    realtimeCollectionsReadyPromise: Promise<JsonValue | null> | null = null;
    ui: ModelDetailUi | null = null;
    listeners: AbortController | null = null;
    modelId: string | null = null;
    model: ModelRecord | null = null;
    modelSubscription: StreamSubscription | null = null;
    parameters: ParametersData | null = null;
    activeTab = 'overview';
    deletionStream: StreamHandle | null = null;
    metrics: JsonObject | null = null;
    backendDocumentationUrl: string | null = null;
    pluginSnapshot: JsonValue[] = [];
    pendingAction: string | null = null;
    loadError: Error | null = null;

    resetForInitialization(modelId: string | null): void {
        this.ui = null;
        this.listeners?.abort();
        this.listeners = null;
        this.loadError = null;
        this.modelId = modelId;
    }
}

export { ModelDetailSession };
