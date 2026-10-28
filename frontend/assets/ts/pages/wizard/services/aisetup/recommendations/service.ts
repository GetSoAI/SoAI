/* SoAI - Wizard AI setup model recommendations [frontend/assets/ts/pages/wizard/services/aisetup/recommendations/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareFacts } from '@pages/wizard/services/aisetup/facts/mappers.ts';
import type { ModelCatalogEntry } from '@pages/wizard/services/aisetup/catalog/constants.ts';
import type { AutomaticEngine } from '@pages/wizard/services/aisetup/engines/service.ts';

const GIBIBYTE = 1024 * 1024 * 1024;
const RUNTIME_OVERHEAD_BYTES = GIBIBYTE;
const STARTER_CONTEXT_TOKENS = 16384;
const REDUCED_CONTEXT_TOKENS = 8192;
const MAX_RECOMMENDATION_CARDS = 3;
const GPU_FAST_ACTIVE_PARAMETERS_B = 12;
const CPU_MODERATE_ACTIVE_PARAMETERS_B = 4;

type RecommendationRole = 'recommended' | 'faster' | 'smallest';
type RecommendationRunsOn = 'gpu' | 'cpu';
type RecommendationSpeed = 'fast' | 'moderate' | 'slow';
type RecommendationEmptyReason = 'no_compatible_engine' | 'insufficient_memory' | 'assessment_unknown';

interface RecommendationCard {
    entry: ModelCatalogEntry;
    role: RecommendationRole | null;
    runsOn: RecommendationRunsOn;
    speed: RecommendationSpeed;
    contextTokens: number;
}

interface RecommendationSelection {
    cards: RecommendationCard[];
    emptyReason: RecommendationEmptyReason | null;
    emptyDetail: { requiredBytes: number; availableBytes: number } | null;
}

interface FittingEntry {
    entry: ModelCatalogEntry;
    contextTokens: number;
}

const reducedContextMemoryBytes = (entry: ModelCatalogEntry): number => entry.memoryNeededBytes - (entry.memoryNeededBytes - entry.downloadBytes - RUNTIME_OVERHEAD_BYTES) / 2;

const gpuBudgetBytes = (memoryBytes: number): number => memoryBytes - Math.max(GIBIBYTE, memoryBytes * 0.15);

const cpuBudgetBytes = (memoryBytes: number): number => memoryBytes - Math.max(2 * GIBIBYTE, memoryBytes * 0.2);

const resolveGpuBudget = (hardware: HardwareFacts): number | null => {
    if (hardware.gpus.some((gpu) => gpu.unifiedMemory)) {
        return hardware.systemRamBytes === null ? null : gpuBudgetBytes(hardware.systemRamBytes);
    }
    const budgets = hardware.gpus.flatMap((gpu) => (gpu.vramBytes === null ? [] : [gpuBudgetBytes(gpu.vramBytes)]));
    return budgets.length > 0 ? Math.max(...budgets) : null;
};

const fitEntries = (catalog: readonly ModelCatalogEntry[], budget: number): FittingEntry[] =>
    catalog.flatMap((entry) => {
        if (entry.memoryNeededBytes <= budget) return [{ entry, contextTokens: STARTER_CONTEXT_TOKENS }];
        if (reducedContextMemoryBytes(entry) <= budget) return [{ entry, contextTokens: REDUCED_CONTEXT_TOKENS }];
        return [];
    });

const readSpeed = (entry: ModelCatalogEntry, runsOn: RecommendationRunsOn): RecommendationSpeed => {
    if (runsOn === 'gpu') return entry.parametersActiveB <= GPU_FAST_ACTIVE_PARAMETERS_B ? 'fast' : 'moderate';
    return entry.parametersActiveB <= CPU_MODERATE_ACTIVE_PARAMETERS_B ? 'moderate' : 'slow';
};

const byQuality = (left: FittingEntry, right: FittingEntry): number => left.entry.qualityOrder - right.entry.qualityOrder;

const cpuSpeedRank = (entry: ModelCatalogEntry): number => (entry.parametersActiveB <= CPU_MODERATE_ACTIVE_PARAMETERS_B ? 0 : 1);

const byCpuSpeedClass = (left: FittingEntry, right: FittingEntry): number => cpuSpeedRank(left.entry) - cpuSpeedRank(right.entry) || byQuality(left, right);

const byActiveParameters = (left: FittingEntry, right: FittingEntry): number => left.entry.parametersActiveB - right.entry.parametersActiveB || byQuality(left, right);

const byDownloadSize = (left: FittingEntry, right: FittingEntry): number => left.entry.downloadBytes - right.entry.downloadBytes || byQuality(left, right);

const pickDistinct = (fitting: readonly FittingEntry[], chosen: readonly FittingEntry[], compare: (left: FittingEntry, right: FittingEntry) => number): FittingEntry | null => {
    const remaining = fitting.filter((candidate) => !chosen.includes(candidate)).sort(compare);
    const usedFamilies = new Set(chosen.map((candidate) => candidate.entry.family));
    return remaining.find((candidate) => !usedFamilies.has(candidate.entry.family)) ?? remaining[0] ?? null;
};

const assignRoles = (fitting: readonly FittingEntry[], runsOn: RecommendationRunsOn): RecommendationCard[] => {
    const rolePicks: readonly [RecommendationRole, (left: FittingEntry, right: FittingEntry) => number][] = [
        ['recommended', runsOn === 'cpu' ? byCpuSpeedClass : byQuality],
        ['faster', byActiveParameters],
        ['smallest', byDownloadSize]
    ];
    const chosen: FittingEntry[] = [];
    const cards: RecommendationCard[] = [];
    for (const [role, compare] of rolePicks) {
        const pick = pickDistinct(fitting, chosen, compare);
        if (!pick) break;
        chosen.push(pick);
        cards.push({ entry: pick.entry, role, runsOn, speed: readSpeed(pick.entry, runsOn), contextTokens: pick.contextTokens });
    }
    return cards;
};

const selectUnassessed = (catalog: readonly ModelCatalogEntry[], runsOn: RecommendationRunsOn): RecommendationSelection => {
    const smallest = [...catalog].sort((left, right) => left.downloadBytes - right.downloadBytes || left.qualityOrder - right.qualityOrder).slice(0, MAX_RECOMMENDATION_CARDS);
    return { cards: smallest.map((entry) => ({ entry, role: null, runsOn, speed: readSpeed(entry, runsOn), contextTokens: STARTER_CONTEXT_TOKENS })), emptyReason: 'assessment_unknown', emptyDetail: null };
};

const selectRecommendations = (catalog: readonly ModelCatalogEntry[], hardware: HardwareFacts, engine: AutomaticEngine): RecommendationSelection => {
    if (engine.status === 'none') {
        return { cards: [], emptyReason: 'no_compatible_engine', emptyDetail: null };
    }
    const entries = catalog.filter((entry) => entry.pluginName === engine.pluginName);
    if (entries.length === 0) {
        return { cards: [], emptyReason: null, emptyDetail: null };
    }
    const gpuBudget = engine.gpuBudgetEligible ? resolveGpuBudget(hardware) : null;
    const gpuFitting = gpuBudget === null ? [] : fitEntries(entries, gpuBudget);
    if (gpuFitting.length > 0) {
        return { cards: assignRoles(gpuFitting, 'gpu'), emptyReason: null, emptyDetail: null };
    }
    if (hardware.systemRamBytes === null) {
        return selectUnassessed(entries, engine.gpuBudgetEligible ? 'gpu' : 'cpu');
    }
    const cpuBudget = cpuBudgetBytes(hardware.systemRamBytes);
    const cpuFitting = fitEntries(entries, cpuBudget);
    if (cpuFitting.length > 0) {
        return { cards: assignRoles(cpuFitting, 'cpu'), emptyReason: null, emptyDetail: null };
    }
    const requiredBytes = Math.min(...entries.map(reducedContextMemoryBytes));
    return { cards: [], emptyReason: 'insufficient_memory', emptyDetail: { requiredBytes, availableBytes: Math.max(0, gpuBudget ?? 0, cpuBudget) } };
};

const resolveStarterContextTokens = (entry: ModelCatalogEntry, hardware: HardwareFacts, engine: AutomaticEngine): number => selectRecommendations([entry], hardware, engine).cards[0]?.contextTokens ?? REDUCED_CONTEXT_TOKENS;

const isLimitedSelection = (selection: RecommendationSelection): boolean => selection.emptyReason === 'no_compatible_engine' || selection.emptyReason === 'insufficient_memory';

export { isLimitedSelection, REDUCED_CONTEXT_TOKENS, reducedContextMemoryBytes, resolveStarterContextTokens, selectRecommendations, STARTER_CONTEXT_TOKENS };
export type { RecommendationCard, RecommendationEmptyReason, RecommendationRole, RecommendationRunsOn, RecommendationSelection, RecommendationSpeed };
