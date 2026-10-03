/* SoAI - Wizard AI setup device and engine facts [frontend/assets/ts/pages/wizard/services/aisetup/facts/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BackendVariantsResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import type { HardwareSnapshotResponse } from '@core/api/contracts/hardwareContractTypes.ts';
import { getApiClient } from '@core/api/service.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { formatTitleFromId } from '@core/primitives/text.ts';
import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { isModelPluginOperational, requireCatalogStore } from '@features/catalog/public.ts';
import { readHardwareFacts, type HardwareFacts } from '@pages/wizard/services/aisetup/facts/mappers.ts';
import { MODEL_CATALOG } from '@pages/wizard/services/aisetup/catalog/constants.ts';
import { AUTOMATIC_ENGINE_ORDER, describeEngineOptions, resolveAutomaticEngine, type AutomaticEngine, type EngineCandidate, type EngineOption } from '@pages/wizard/services/aisetup/engines/service.ts';
import { selectRecommendations, type RecommendationSelection } from '@pages/wizard/services/aisetup/recommendations/service.ts';

interface AiSetupFacts {
    hardware: HardwareFacts;
    candidates: readonly EngineCandidate[];
    automatic: AutomaticEngine;
    engineOptions: readonly EngineOption[];
    engineNames: ReadonlyMap<string, string>;
}

const resolvePluginDisplayName = (plugin: PluginRecord | null, pluginName: string): string => toTrimmedString(plugin?.displayName) || formatTitleFromId(pluginName);

const readOptionalFact = async <T>(label: string, load: () => Promise<T>): Promise<T | null> => {
    try {
        return await load();
    } catch (error) {
        errorHandler.warn('WizardAiSetup', `${label} is unavailable; continuing without it`, ensureError(error));
        return null;
    }
};

const CATALOG_LOAD_ATTEMPTS = 3;

const loadPluginCatalog = async (signal: AbortSignal): Promise<ReadonlyArray<PluginRecord>> => {
    for (let attempt = 1; ; attempt += 1) {
        try {
            return await requireCatalogStore().ensureLoaded();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isLifecycleCancellationError(runtimeError) || attempt >= CATALOG_LOAD_ATTEMPTS || signal.aborted) throw runtimeError;
        }
    }
};

const loadEngineCandidate = async (pluginName: string): Promise<EngineCandidate> => {
    const variants = await readOptionalFact<BackendVariantsResponse>(`Backend variants for ${pluginName}`, () => getApiClient().plugins.getBackendVariants(pluginName));
    return { pluginName, variants, operational: isModelPluginOperational(requireCatalogStore().getPlugin(pluginName)) };
};

const deriveAiSetupFacts = (hardware: HardwareFacts, candidates: readonly EngineCandidate[], engineNames: ReadonlyMap<string, string>): AiSetupFacts => {
    const hasGpu = hardware.gpus.length > 0;
    const automatic = resolveAutomaticEngine(candidates, hasGpu);
    return { hardware, candidates, automatic, engineOptions: describeEngineOptions(candidates, hasGpu, automatic), engineNames };
};

const loadAiSetupFacts = async (signal: AbortSignal): Promise<AiSetupFacts> => {
    const [snapshot, plugins] = await Promise.all([readOptionalFact<HardwareSnapshotResponse>('Hardware snapshot', () => getApiClient().hardware.snapshot({ components: ['memory', 'gpu'], signal })), loadPluginCatalog(signal)]);
    throwIfAborted(signal);
    const engines = AUTOMATIC_ENGINE_ORDER.flatMap((pluginName) => {
        const plugin = plugins.find((entry) => entry.name === pluginName);
        return plugin === undefined ? [] : [{ pluginName, displayName: resolvePluginDisplayName(plugin, pluginName) }];
    });
    const candidates = await Promise.all(engines.map((engine) => loadEngineCandidate(engine.pluginName)));
    throwIfAborted(signal);
    return deriveAiSetupFacts(readHardwareFacts(snapshot), candidates, new Map(engines.map((engine) => [engine.pluginName, engine.displayName])));
};

const withEngineCandidate = (facts: AiSetupFacts, refreshed: EngineCandidate): AiSetupFacts =>
    deriveAiSetupFacts(
        facts.hardware,
        facts.candidates.map((candidate) => (candidate.pluginName === refreshed.pluginName ? refreshed : candidate)),
        facts.engineNames
    );

const resolveItemEngine = (facts: AiSetupFacts, pluginName: string): AutomaticEngine => facts.engineOptions.find((option) => option.pluginName === pluginName)?.engine ?? { status: 'none' };

const readEngineName = (facts: AiSetupFacts | null, pluginName: string): string => facts?.engineNames.get(pluginName) ?? resolvePluginDisplayName(requireCatalogStore().getPlugin(pluginName), pluginName);

const resolveModelEngine = (facts: AiSetupFacts, setup: AiSetupState): AutomaticEngine => {
    if (setup.engine.mode === 'automatic') return facts.automatic;
    const chosen = new Set(setup.engine.backends.filter((backend) => !backend.excluded).map((backend) => backend.pluginName));
    return facts.engineOptions.find((option) => chosen.has(option.pluginName) && option.engine.status !== 'none')?.engine ?? { status: 'none' };
};

const resolveRecommendations = (facts: AiSetupFacts, setup: AiSetupState): RecommendationSelection => selectRecommendations(MODEL_CATALOG, facts.hardware, resolveModelEngine(facts, setup));

const resolveSearchPluginName = (facts: AiSetupFacts, setup: AiSetupState): string => {
    const engine = resolveModelEngine(facts, setup);
    return engine.status === 'none' ? (MODEL_CATALOG[0]?.pluginName ?? '') : engine.pluginName;
};

const isEngineInstalled = (facts: AiSetupFacts, pluginName: string): boolean => facts.engineOptions.some((option) => option.pluginName === pluginName && option.status === 'installed');

export { isEngineInstalled, loadAiSetupFacts, loadEngineCandidate, readEngineName, resolveItemEngine, resolveModelEngine, resolvePluginDisplayName, resolveRecommendations, resolveSearchPluginName, withEngineCandidate };
export type { AiSetupFacts };
