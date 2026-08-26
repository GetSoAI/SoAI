/* SoAI - Model detail page control layer view public contracts [frontend/assets/ts/pages/modeldetail/controllers/page/view/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { OpenAICapabilityOverrideCategory, OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import type { ModelDetailUi } from '@pages/modeldetail/dom.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';

interface ModelDetailSharedUiHost extends PageDomOwnerHost {
    sanitizeText: (value: JsonValue | null | undefined) => string;
}

interface ModelDetailViewStatePort extends PageDomOwnerHost {
    model: ModelRecord | null;
    pluginCollectionSnapshot: JsonValue[];
    backendDocumentationUrl: string | null;
    parameterState: ParameterStateManager;
    activeTab: string;
    streamManager: StreamRuntimeOwners;
    ensureUi: () => ModelDetailUi;
    isVirtualModel: () => boolean;
}

interface ModelDetailViewPresentationPort {
    sanitizeText: (value: string | null | undefined) => string;
    sanitizeClassName: (value: string, fallback: string) => string;
    sanitizeAttribute: (value: string) => string;
    setInfo: (id: string, value: JsonValue | null | undefined, formatter?: (value: JsonValue | null | undefined) => string | null) => void;
    getModelPluginName: () => string;
    findPluginRecord: (pluginName: string) => PluginRecord | null;
    getModelDisplayName: () => string;
    getPluginStatus: () => string | null;
    describePluginStatus: (value: string) => string;
    updateHeaderInfo: () => void;
}

interface ModelDetailViewActionPort {
    getManageAliasButton: () => HTMLElement | null;
    getStopPluginButton: () => HTMLElement | null;
    getModelSourceModelId: () => string | undefined;
    setUiValue: (element: Element, value: string, options?: { attribute?: string }) => void;
    modalPresenter: ModalPresenterApi;
    getOpenAICapabilityState: () => OpenAICapabilityOverrideState | null;
    resolveOpenAICapabilityLabel(category: OpenAICapabilityOverrideCategory, token: string): string;
}

interface ModelDetailViewHost {
    state: ModelDetailViewStatePort;
    presentation: ModelDetailViewPresentationPort;
    actions: ModelDetailViewActionPort;
}

interface ModelDetailViewDependencies extends PageServicesOwnerHost, PageUiOwnerHost, PageDomOwnerHost {
    session: ModelDetailSession;
    parameterState: ParameterStateManager;
    streamManager: ModelDetailViewHost['state']['streamManager'];
    ensureUi: ModelDetailViewHost['state']['ensureUi'];
    isVirtualModel: ModelDetailViewHost['state']['isVirtualModel'];
    sanitizeAttribute: ModelDetailViewHost['presentation']['sanitizeAttribute'];
    statusManager: { getDescription: (value: string) => string | null } | null;
    modalPresenter: ModalPresenterApi;
    getOpenAICapabilityState: ModelDetailViewHost['actions']['getOpenAICapabilityState'];
    resolveOpenAICapabilityLabel: ModelDetailViewHost['actions']['resolveOpenAICapabilityLabel'];
}

export type { ModelDetailSharedUiHost, ModelDetailViewDependencies, ModelDetailViewHost };
