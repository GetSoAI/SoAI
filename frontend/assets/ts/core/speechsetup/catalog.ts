/* SoAI - Speech setup queries over current catalog snapshots [frontend/assets/ts/core/speechsetup/catalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ClientDataHub } from '@core/data/ClientDataHub.ts';
import { readDecodedModelCollection } from '@core/models/decodedModelCollection.ts';
import { supportsOpenAIEndpointForModel, isOpenAICapabilityEnabled } from '@core/openai/capabilityChecks.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INSTALL_ERROR } from '@core/state/pluginStatus.ts';
import type { SpeechSetupCandidate, SpeechSetupProtocol, SpeechSetupScope, SpeechSetupSnapshot } from '@core/speechsetup/protocols.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';

interface SpeechCatalogSource {
    isFresh(): boolean;
    getPlugins(): readonly PluginRecord[];
    ensureLoaded(): Promise<readonly PluginRecord[]>;
    subscribe(listener: () => void): () => void;
}

const isPresent = (plugin: PluginRecord): boolean => !['ABSENT', 'NOT_DETECTED', 'DELETING', 'INCOMPATIBLE'].includes(plugin.state ?? '');
const backendMissing = (state: string): boolean => state === PLUGIN_STATUS_BACKEND_NOT_INSTALLED || state === PLUGIN_STATUS_INSTALL_ERROR;

const candidate = (plugin: PluginRecord): SpeechSetupCandidate => {
    const state = plugin.state ?? '';
    return {
        pluginName: plugin.name ?? '',
        displayName: plugin.displayName || plugin.name || '',
        state,
        backendInstallable: plugin.capabilities?.supportsBackendInstallation === true && backendMissing(state),
        modelsDownloadable: plugin.capabilities?.supportsModelDownload === true && !backendMissing(state) && state !== PLUGIN_STATUS_DISABLED,
        enableRequired: state === PLUGIN_STATUS_DISABLED
    };
};

const createSpeechSetupService = (hub: Pick<ClientDataHub, 'snapshot' | 'ensureResource' | 'subscribe'>, catalog: SpeechCatalogSource): SpeechSetupProtocol => ({
    snapshot: (scope: SpeechSetupScope = 'media'): SpeechSetupSnapshot => {
        const endpoint = scope === 'synthesis' ? 'audio_speech' : 'audio_transcriptions';
        const collection = hub.snapshot(MODELS);
        const fresh = catalog.isFresh() && collection.status === 'ready' && collection.hasAuthoritativeSnapshot && collection.staleSinceMonotonicMs === null;
        const plugins = catalog.getPlugins().filter((plugin) => isPresent(plugin) && (scope !== 'media' || plugin.capabilities?.localModels === true) && isOpenAICapabilityEnabled(plugin.capabilities?.openai, 'endpoints', endpoint));
        const candidates = plugins.map(candidate).sort((first, second) => (first.pluginName < second.pluginName ? -1 : first.pluginName > second.pluginName ? 1 : 0));
        const decoded = readDecodedModelCollection(toJsonCompatibleValue(collection.items));
        const capableModels = (decoded ?? []).filter((model) => {
            if (!supportsOpenAIEndpointForModel(model, endpoint)) return false;
            if (scope === 'media' && (model.type !== 'local' || model.providerId)) return false;
            if (scope !== 'media' && model.type === 'virtual') return true;
            return plugins.some((plugin) => plugin.name === (model.pluginName ?? model.plugin) && !backendMissing(plugin.state ?? '') && plugin.state !== PLUGIN_STATUS_DISABLED);
        });
        const models = capableModels.filter((model) => model.isEnabled !== false && model.isOrphaned !== true && (model.status === undefined || model.status === 'active'));
        const reason = models.length > 0 ? null : capableModels.length > 0 ? 'model_disabled' : candidates.length === 0 ? (scope === 'synthesis' ? 'no_tts_plugin' : 'no_stt_plugin') : candidates.some((entry) => !backendMissing(entry.state) && !entry.enableRequired) ? 'no_model_installed' : candidates.some((entry) => entry.enableRequired) ? 'plugin_disabled' : 'backend_not_installed';
        return { fresh: fresh && decoded !== null, models, candidates, reason };
    },
    ensureReady: async (): Promise<void> => {
        await Promise.all([hub.ensureResource(MODELS), catalog.ensureLoaded()]);
    },
    subscribe: (listener): (() => void) => {
        const unsubscribeModels = hub.subscribe(MODELS, listener);
        const unsubscribePlugins = catalog.subscribe(listener);
        return (): void => {
            unsubscribeModels();
            unsubscribePlugins();
        };
    }
});

export { createSpeechSetupService };
