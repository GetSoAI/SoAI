/* SoAI - Wizard AI setup step view model derivation [frontend/assets/ts/pages/wizard/services/aisetup/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { AiSetupCompletionView, AiSetupConnectView, AiSetupModelsView, AiSetupSourcesView } from '@pages/wizard/contracts/aisetup/types.ts';
import { listProviderModels, readModelLabel } from '@pages/wizard/services/aisetup/catalog/mappers.ts';
import type { CloudConnectionState, ProviderPluginAvailability } from '@pages/wizard/services/aisetup/AiSetupCloudConnectionSession.ts';
import { readEngineName, resolveRecommendations, type AiSetupFacts } from '@pages/wizard/services/aisetup/facts/service.ts';
import type { AiSetupProgressSummary } from '@pages/wizard/services/aisetup/progress/mappers.ts';
import type { ModelSearchState } from '@pages/wizard/services/aisetup/AiSetupModelSearchController.ts';
import { activeProvider, resolveDefaultFirstChatItemId, selectedModels } from '@pages/wizard/services/aisetup/state.ts';
import { findModelCatalogEntry } from '@pages/wizard/services/aisetup/catalog/constants.ts';
import type { AutomaticEngine } from '@pages/wizard/services/aisetup/engines/service.ts';
import type { RecommendationSelection } from '@pages/wizard/services/aisetup/recommendations/service.ts';

interface AiSetupSnapshot {
    setup: AiSetupState;
    facts: AiSetupFacts;
    models: readonly ModelData[];
    progress: AiSetupProgressSummary;
    connection: CloudConnectionState;
    providerAvailability: ProviderPluginAvailability;
    search: ModelSearchState;
    searchOpen: boolean;
    cloudFilter: string;
    resolveRepositoryUrl(pluginName: string, repository: string): string | null;
}

const readLimitedMessage = (selection: RecommendationSelection): string | null => {
    if (selection.emptyReason === 'no_compatible_engine') return i18n.t('wizard.aiSetup.limited.noCompatibleEngine');
    if (selection.emptyReason === 'insufficient_memory' && selection.emptyDetail !== null) {
        return i18n.t('wizard.aiSetup.limited.insufficientMemory', { required: formatBytes(selection.emptyDetail.requiredBytes), available: formatBytes(selection.emptyDetail.availableBytes) });
    }
    return null;
};

const describeAutomaticEngine = (facts: AiSetupFacts, engine: AutomaticEngine): string | null => {
    if (engine.status === 'none') return null;
    const name = readEngineName(facts, engine.pluginName);
    if (engine.status === 'installed') return i18n.t('wizard.aiSetup.connect.local.usesInstalled', { engine: name });
    return engine.usesGpu ? i18n.t('wizard.aiSetup.connect.local.usesGpu', { engine: name }) : i18n.t('wizard.aiSetup.connect.local.usesProcessor', { engine: name });
};

const buildSourcesView = (snapshot: AiSetupSnapshot): AiSetupSourcesView => ({
    sources: snapshot.setup.sources,
    limitedMessage: readLimitedMessage(resolveRecommendations(snapshot.facts, { ...snapshot.setup, engine: { mode: 'automatic', backends: [] } }))
});

const buildConnectView = (snapshot: AiSetupSnapshot): AiSetupConnectView => {
    const { setup, facts } = snapshot;
    const provider = activeProvider(setup);
    const chosen = new Set(setup.engine.backends.filter((backend) => !backend.excluded).map((backend) => backend.pluginName));
    return {
        showCloud: setup.sources.cloud,
        showLocal: setup.sources.local,
        providerAvailability: snapshot.providerAvailability,
        connection: snapshot.connection,
        provider,
        providerModelCount: provider === null ? 0 : listProviderModels(snapshot.models, provider).length,
        engineMode: setup.engine.mode,
        automaticLine: describeAutomaticEngine(facts, facts.automatic),
        engines: facts.engineOptions.map((option) => ({ pluginName: option.pluginName, name: readEngineName(facts, option.pluginName), status: option.status, reason: option.reason ?? describeAutomaticEngine(facts, option.engine), selected: setup.engine.mode === 'manual' && chosen.has(option.pluginName) }))
    };
};

const buildModelsView = (snapshot: AiSetupSnapshot): AiSetupModelsView => {
    const { setup } = snapshot;
    const selection = resolveRecommendations(snapshot.facts, setup);
    const localItems = setup.models.filter((model) => model.source === 'local' && !model.excluded);
    const cardIds = new Set(selection.cards.map((card) => card.entry.id));
    const provider = activeProvider(setup);
    const cloudItems = setup.models.filter((model) => model.source === 'cloud' && !model.excluded);
    return {
        showLocal: setup.sources.local,
        showCloud: setup.sources.cloud && provider !== null,
        localCards: selection.cards.map((card) => ({ card, itemId: localItems.find((item) => item.catalogId === card.entry.id)?.itemId ?? null, repositoryUrl: snapshot.resolveRepositoryUrl(card.entry.pluginName, card.entry.repository) })),
        pickedModels: localItems.filter((item) => item.catalogId === null || !cardIds.has(item.catalogId)).map((item) => ({ itemId: item.itemId, label: findModelCatalogEntry(item.catalogId)?.name ?? item.artifactName ?? item.artifactReference ?? item.itemId, detail: item.repositoryId ?? '' })),
        limitedMessage: readLimitedMessage(selection),
        searchOpen: snapshot.searchOpen || (selection.cards.length === 0 && selection.emptyReason === null),
        search: snapshot.search,
        providerName: provider?.providerName ?? null,
        cloudModels: provider === null ? [] : listProviderModels(snapshot.models, provider).map((model) => ({ modelId: model.id, label: readModelLabel(model, model.id), itemId: cloudItems.find((item) => item.modelId === model.id)?.itemId ?? null })),
        cloudFilter: snapshot.cloudFilter,
        firstChatItemId: resolveDefaultFirstChatItemId(setup),
        showOpenChat: selectedModels(setup).length > 1
    };
};

const buildCompletionView = (progress: AiSetupProgressSummary): AiSetupCompletionView => ({
    readyNames: progress.rows.filter((row) => row.kind === 'model' && row.ready).map((row) => row.label),
    preparingCount: progress.modelCount - progress.readyCount
});

export { buildCompletionView, buildConnectView, buildModelsView, buildSourcesView, readLimitedMessage };
export type { AiSetupSnapshot };
