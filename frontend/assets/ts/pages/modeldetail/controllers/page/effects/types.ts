/* SoAI - Model detail page control layer effects public contracts [frontend/assets/ts/pages/modeldetail/controllers/page/effects/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ModelDetailParametersData } from '@pages/modeldetail/types.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { ModelDetailParameterAuthority } from '@pages/modeldetail/state/ModelDetailParameterAuthorityState.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { ModelDetailViewHost } from '@pages/modeldetail/controllers/page/view/types.ts';

type ParametersData = ModelDetailParametersData;

interface ModelDetailEffectsStatePort extends PageResourcesOwnerHost {
    isDestroyed: boolean;
    signal: AbortSignal | null;
    modelId: string | null;
    model: ModelRecord | null;
    parametersData: ParametersData | null;
    parameterAuthority: ModelDetailParameterAuthority;
    isParameterEditorDirty: () => boolean;
    activeTab: string;
    pluginCollectionSnapshot: JsonValue[];
    currentMetrics: JsonObject | null;
    streamManager: StreamRuntimeOwners;
    parameterView: { setModel: (model: ModelRecord | null) => void };
    ensureRealtimeCollectionsReady: () => Promise<JsonValue | null>;
}

interface ModelDetailEffectsRenderPort {
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    setLoadError: (error: Error | null) => void;
    setPageState: (state: string) => void;
    applyParametersPayload: (payload: ParametersData) => void;
    populateModelInfo: () => void;
    renderParametersInterface: () => void;
    renderParameterAvailability: () => void;
    notifySaveChanged: () => void;
    notifyParametersUnavailable: (message: string) => void;
    persistSnapshots: (modelSnapshot: ModelRecord | null, parameterSnapshot: ParametersData | null) => void;
    updateBackendDocumentationLink: (options?: { ensurePlugins?: boolean; plugins?: JsonValue[] | null }) => Promise<void>;
    updateTestPluginStatusDisplay: () => void;
    populateDetailCards: () => void;
    setInfo: (id: string, value: JsonValue | null | undefined) => void;
    getModelPluginName: () => string;
    onModelDeleted: () => void;
}

interface ModelDetailEffectsHost {
    state: ModelDetailEffectsStatePort;
    rendering: ModelDetailEffectsRenderPort;
}

interface ModelDetailParameterAvailabilityPort {
    renderParameterAvailability: ModelDetailEffectsHost['rendering']['renderParameterAvailability'];
    notifySaveChanged: ModelDetailEffectsHost['rendering']['notifySaveChanged'];
}

interface ModelDetailEffectsDependencies extends PageResourcesOwnerHost, PageFeedbackOwnerHost, PageLifecycleOwnerHost, PageStreamingOwnerHost {
    session: ModelDetailSession;
    view: ModelDetailViewHost;
    isDestroyed: boolean;
    streamManager: StreamRuntimeOwners;
    parameterView: ModelDetailEffectsHost['state']['parameterView'] & { hasParameterChanges: () => boolean };
    reconcileOpenAICapabilityState: (model: ModelRecord | null) => void;
    setLoadError: ModelDetailEffectsHost['rendering']['setLoadError'];
    applyParametersPayload: ModelDetailEffectsHost['rendering']['applyParametersPayload'];
    populateModelInfo: ModelDetailEffectsHost['rendering']['populateModelInfo'];
    renderParametersInterface: ModelDetailEffectsHost['rendering']['renderParametersInterface'];
    parameterAvailability: ModelDetailParameterAvailabilityPort;
    updateBackendDocButtonVisibility: () => void;
    updateTestPluginStatusDisplay: ModelDetailEffectsHost['rendering']['updateTestPluginStatusDisplay'];
    populateDetailCards: ModelDetailEffectsHost['rendering']['populateDetailCards'];
    setInfo: ModelDetailEffectsHost['rendering']['setInfo'];
    router: { navigate: (pageId: string) => void } | null;
}

export type { ModelDetailEffectsDependencies, ModelDetailEffectsHost, ParametersData };
