/* SoAI - Wizard AI setup device and engine facts [frontend/assets/ts/pages/wizard/services/aisetup/facts/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareSnapshotResponse } from '@core/api/contracts/hardwareContractTypes.ts';
import { readApiErrorDetail } from '@core/api/errorPayloads.ts';
import { APIError } from '@core/apiError.ts';
import { getApiClient } from '@core/api/service.ts';
import { TIMEOUTS } from '@core/constants.ts';
import { isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';
import { formatTitleFromId } from '@core/primitives/text.ts';
import type { AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { isModelPluginOperational, requireCatalogStore } from '@features/catalog/public.ts';
import { hardwareFactsRequireRetry, readHardwareFacts, type HardwareFacts } from '@pages/wizard/services/aisetup/facts/mappers.ts';
import { MODEL_CATALOG } from '@pages/wizard/services/aisetup/catalog/constants.ts';
import { AUTOMATIC_ENGINE_ORDER, describeEngineOptions, resolveAutomaticEngine, type AutomaticEngine, type EngineCandidate, type EngineOption } from '@pages/wizard/services/aisetup/engines/service.ts';
import { selectRecommendations, type RecommendationSelection } from '@pages/wizard/services/aisetup/recommendations/service.ts';

interface AiSetupFacts {
    hardwareRetryNeeded?: boolean;
    hardware: HardwareFacts;
    candidates: readonly EngineCandidate[];
    automatic: AutomaticEngine;
    engineOptions: readonly EngineOption[];
    engineNames: ReadonlyMap<string, string>;
}

const resolvePluginDisplayName = (plugin: PluginRecord | null, pluginName: string): string => toTrimmedString(plugin?.displayName) || formatTitleFromId(pluginName);

const readOptionalFact = async <T>(label: string, signal: AbortSignal, load: () => Promise<T>): Promise<T | null> => {
    throwIfAborted(signal);
    try {
        return await raceWithAbortSignal(load(), signal);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (signal.aborted || isAbortError(runtimeError) || isLifecycleCancellationError(runtimeError)) throw runtimeError;
        errorHandler.warn('WizardAiSetup', `${label} is unavailable; continuing without it`, runtimeError);
        return null;
    }
};

const isAiSetupDiscoveryReady = (facts: AiSetupFacts): boolean => facts.hardwareRetryNeeded !== true && facts.candidates.every((candidate) => candidate.variants !== null || candidate.rejection?.type === 'plugin_incompatible');

const CATALOG_RETRY_INITIAL_DELAY_MS = 250;
const CATALOG_RETRY_MAX_DELAY_MS = 2000;

const loadPluginCatalog = async (signal: AbortSignal): Promise<ReadonlyArray<PluginRecord>> => {
    const deadlineMs = performance.now() + TIMEOUTS.STREAM_CONNECT;
    for (let delayMs = CATALOG_RETRY_INITIAL_DELAY_MS; ; delayMs = Math.min(delayMs * 2, CATALOG_RETRY_MAX_DELAY_MS)) {
        try {
            throwIfAborted(signal);
            return await raceWithAbortSignal(requireCatalogStore().ensureLoaded(), signal);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isLifecycleCancellationError(runtimeError) || signal.aborted || performance.now() + delayMs >= deadlineMs) throw runtimeError;
        }
        await sleepMsAbortable(signal, delayMs);
    }
};

const loadEngineCandidate = async (pluginName: string, signal: AbortSignal): Promise<EngineCandidate> => {
    const discovery = await readOptionalFact<Pick<EngineCandidate, 'variants' | 'rejection'>>(`Backend variants for ${pluginName}`, signal, async () => {
        try {
            return { variants: await getApiClient().plugins.getBackendVariants(pluginName, { signal }) };
        } catch (error) {
            const reason = readApiErrorDetail(error, 'reason');
            if (error instanceof APIError && error.status === 409 && error.code === 'plugin_incompatible' && readApiErrorDetail(error, 'plugin') === pluginName && typeof reason === 'string' && reason.trim() && readApiErrorDetail(error, 'is_overridden') === false) return { variants: null, rejection: { type: 'plugin_incompatible', message: error.message } };
            throw error;
        }
    });
    return { pluginName, ...(discovery ?? { variants: null }), operational: isModelPluginOperational(requireCatalogStore().getPlugin(pluginName)) };
};

const deriveAiSetupFacts = (hardware: HardwareFacts, candidates: readonly EngineCandidate[], engineNames: ReadonlyMap<string, string>): AiSetupFacts => {
    const hasGpu = hardware.gpus.length > 0;
    const automatic = resolveAutomaticEngine(candidates, hasGpu);
    return {
        hardware,
        candidates,
        automatic,
        engineOptions: describeEngineOptions(
            candidates,
            hardware.gpus.map((gpu) => gpu.brand),
            automatic
        ),
        engineNames
    };
};

const loadEngineFacts = async (signal: AbortSignal): Promise<{ candidates: EngineCandidate[]; names: ReadonlyMap<string, string> }> => {
    const plugins = await loadPluginCatalog(signal);
    throwIfAborted(signal);
    const engines = AUTOMATIC_ENGINE_ORDER.flatMap((pluginName) => {
        const plugin = plugins.find((entry) => entry.name === pluginName);
        return plugin === undefined ? [] : [{ pluginName, displayName: resolvePluginDisplayName(plugin, pluginName) }];
    });
    const candidates = await Promise.all(engines.map((engine) => loadEngineCandidate(engine.pluginName, signal)));
    return { candidates, names: new Map(engines.map((engine) => [engine.pluginName, engine.displayName])) };
};

const loadAiSetupFacts = async (signal: AbortSignal): Promise<AiSetupFacts> => {
    const [snapshot, engines] = await Promise.all([readOptionalFact<HardwareSnapshotResponse>('Hardware snapshot', signal, () => getApiClient().hardware.snapshot({ components: ['memory', 'gpu'], includeGpuCapabilities: false, signal })), loadEngineFacts(signal)]);
    throwIfAborted(signal);
    return { ...deriveAiSetupFacts(readHardwareFacts(snapshot), engines.candidates, engines.names), hardwareRetryNeeded: hardwareFactsRequireRetry(snapshot) };
};

const withEngineCandidate = (facts: AiSetupFacts, refreshed: EngineCandidate): AiSetupFacts => ({
    ...facts,
    ...deriveAiSetupFacts(
        facts.hardware,
        facts.candidates.map((candidate) => (candidate.pluginName === refreshed.pluginName ? refreshed : candidate)),
        facts.engineNames
    )
});

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

export { isAiSetupDiscoveryReady, isEngineInstalled, loadAiSetupFacts, loadEngineCandidate, readEngineName, resolveItemEngine, resolveModelEngine, resolvePluginDisplayName, resolveRecommendations, resolveSearchPluginName, withEngineCandidate };
export type { AiSetupFacts };
