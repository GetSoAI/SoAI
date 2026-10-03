/* SoAI - Wizard AI setup step view model contracts [frontend/assets/ts/pages/wizard/contracts/aisetup/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AiSetupEngineMode, AiSetupProvider, AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { CloudConnectionState, ProviderPluginAvailability } from '@pages/wizard/services/aisetup/AiSetupCloudConnectionSession.ts';
import type { AiSetupProgressSummary } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import type { ModelSearchState } from '@pages/wizard/services/aisetup/AiSetupModelSearchController.ts';
import type { EngineOptionStatus } from '@pages/wizard/services/aisetup/engines/service.ts';
import type { RecommendationCard } from '@pages/wizard/services/aisetup/recommendations/service.ts';

interface AiSetupEngineChoiceView {
    pluginName: string;
    name: string;
    status: EngineOptionStatus;
    reason: string | null;
    selected: boolean;
}

interface AiSetupSourcesView {
    sources: AiSetupState['sources'];
    limitedMessage: string | null;
}

interface AiSetupConnectView {
    showCloud: boolean;
    showLocal: boolean;
    providerAvailability: ProviderPluginAvailability;
    connection: CloudConnectionState;
    provider: AiSetupProvider | null;
    providerModelCount: number;
    engineMode: AiSetupEngineMode;
    automaticLine: string | null;
    engines: AiSetupEngineChoiceView[];
}

interface AiSetupLocalCardView {
    card: RecommendationCard;
    itemId: string | null;
    repositoryUrl: string | null;
}

interface AiSetupPickedModelView {
    itemId: string;
    label: string;
    detail: string;
}

interface AiSetupCloudModelView {
    modelId: string;
    label: string;
    itemId: string | null;
}

interface AiSetupModelsView {
    showLocal: boolean;
    showCloud: boolean;
    localCards: AiSetupLocalCardView[];
    pickedModels: AiSetupPickedModelView[];
    limitedMessage: string | null;
    searchOpen: boolean;
    search: ModelSearchState;
    providerName: string | null;
    cloudModels: AiSetupCloudModelView[];
    cloudFilter: string;
    firstChatItemId: string | null;
    showOpenChat: boolean;
}

interface AiSetupCompletionView {
    readyNames: string[];
    preparingCount: number;
}

interface AiSetupViewModel {
    loadFailed: boolean;
    sources: AiSetupSourcesView | null;
    connect: AiSetupConnectView | null;
    models: AiSetupModelsView | null;
    progress: AiSetupProgressSummary | null;
    completion: AiSetupCompletionView | null;
}

export type { AiSetupCloudModelView, AiSetupCompletionView, AiSetupConnectView, AiSetupEngineChoiceView, AiSetupLocalCardView, AiSetupModelsView, AiSetupPickedModelView, AiSetupSourcesView, AiSetupViewModel };
