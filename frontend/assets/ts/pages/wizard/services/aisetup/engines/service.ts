/* SoAI - Wizard AI setup automatic engine choice [frontend/assets/ts/pages/wizard/services/aisetup/engines/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BackendVariantOptionResponse, BackendVariantsResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import { AUTO_BACKEND_VARIANT_ID } from '@features/plugins/public.ts';

const AUTOMATIC_ENGINE_ORDER: readonly string[] = Object.freeze(['llamacpp', 'ollama', 'vllm']);
const CPU_BACKEND_VARIANT_ID = 'cpu';

interface EngineCandidate {
    pluginName: string;
    variants: BackendVariantsResponse | null;
    operational: boolean;
}

type AutomaticEngine = { status: 'installed' | 'install'; pluginName: string; variantId: string; usesGpu: boolean } | { status: 'none' };

type EngineOptionStatus = 'installed' | 'recommended' | 'available' | 'warning' | 'unavailable';

interface EngineOption {
    pluginName: string;
    status: EngineOptionStatus;
    reason: string | null;
    engine: AutomaticEngine;
}

const isSelectableVariant = (option: BackendVariantOptionResponse): boolean => option.id !== AUTO_BACKEND_VARIANT_ID && option.availabilityType === 'available';

const isWarningVariant = (option: BackendVariantOptionResponse): boolean => option.id !== AUTO_BACKEND_VARIANT_ID && option.availabilityType === 'hardware_warning';

const hasUsableGpuVariant = (variants: BackendVariantsResponse): boolean => variants.options.some((option) => option.id !== AUTO_BACKEND_VARIANT_ID && option.id !== CPU_BACKEND_VARIANT_ID && option.availabilityType !== 'unavailable');

const describeEngine = (candidate: EngineCandidate, hasGpu: boolean): AutomaticEngine => {
    const variants = candidate.variants;
    const installedVariantId = variants?.installedVariantId ?? null;
    if (installedVariantId !== null && candidate.operational) {
        return { status: 'installed', pluginName: candidate.pluginName, variantId: installedVariantId, usesGpu: hasGpu && installedVariantId !== CPU_BACKEND_VARIANT_ID };
    }
    if (variants === null || !variants.options.some(isSelectableVariant)) {
        return { status: 'none' };
    }
    return { status: 'install', pluginName: candidate.pluginName, variantId: AUTO_BACKEND_VARIANT_ID, usesGpu: hasGpu && hasUsableGpuVariant(variants) };
};

const orderCandidates = (candidates: readonly EngineCandidate[]): EngineCandidate[] => AUTOMATIC_ENGINE_ORDER.flatMap((pluginName) => candidates.filter((candidate) => candidate.pluginName === pluginName));

const resolveAutomaticEngine = (candidates: readonly EngineCandidate[], hasGpu: boolean): AutomaticEngine => {
    const described = orderCandidates(candidates).map((candidate) => describeEngine(candidate, hasGpu));
    return described.find((engine) => engine.status === 'installed') ?? described.find((engine) => engine.status === 'install') ?? { status: 'none' };
};

const describeWarningEngine = (candidate: EngineCandidate, hasGpu: boolean): EngineOption => {
    const warning = candidate.variants?.options.find(isWarningVariant) ?? null;
    if (warning === null) {
        const reason = candidate.variants?.options.find((option) => option.unavailableReason !== null)?.unavailableReason ?? null;
        return { pluginName: candidate.pluginName, status: 'unavailable', reason, engine: { status: 'none' } };
    }
    return { pluginName: candidate.pluginName, status: 'warning', reason: warning.unavailableReason, engine: { status: 'install', pluginName: candidate.pluginName, variantId: warning.id, usesGpu: hasGpu && warning.id !== CPU_BACKEND_VARIANT_ID } };
};

const describeEngineOptions = (candidates: readonly EngineCandidate[], hasGpu: boolean, automatic: AutomaticEngine): EngineOption[] =>
    orderCandidates(candidates).map((candidate) => {
        const engine = describeEngine(candidate, hasGpu);
        if (engine.status === 'installed') return { pluginName: candidate.pluginName, status: 'installed', reason: null, engine };
        if (engine.status === 'install') {
            const recommended = automatic.status === 'install' && automatic.pluginName === candidate.pluginName;
            return { pluginName: candidate.pluginName, status: recommended ? 'recommended' : 'available', reason: null, engine };
        }
        return describeWarningEngine(candidate, hasGpu);
    });

export { AUTOMATIC_ENGINE_ORDER, describeEngineOptions, resolveAutomaticEngine };
export type { AutomaticEngine, EngineCandidate, EngineOption, EngineOptionStatus };
