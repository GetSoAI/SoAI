/* SoAI - Wizard AI setup automatic engine choice [frontend/assets/ts/pages/wizard/services/aisetup/engines/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BackendVariantOptionResponse, BackendVariantsResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import type { HardwareBrand } from '@core/hardwareBrands.ts';
import { resolveBackendVariantGuidance } from '@core/plugins/backendVariantGuidance.ts';
import { AUTO_BACKEND_VARIANT_ID } from '@features/plugins/public.ts';

const AUTOMATIC_ENGINE_ORDER: readonly string[] = Object.freeze(['llamacpp', 'ollama', 'vllm']);
const CPU_BACKEND_VARIANT_ID = 'cpu';
const GPU_RUNTIME_FAMILY_BRANDS: ReadonlyMap<string, readonly HardwareBrand[]> = new Map<string, readonly HardwareBrand[]>([
    ['cuda', ['nvidia']],
    ['cuda_index', ['nvidia']],
    ['rocm', ['amd']],
    ['xpu', ['intel']],
    ['vulkan_ggml', ['nvidia', 'amd', 'intel', 'qualcomm']]
]);

interface EngineCandidate {
    pluginName: string;
    variants: BackendVariantsResponse | null;
    operational: boolean;
    rejection?: { type: 'plugin_incompatible'; message: string };
}

type EngineExecutionTarget = 'gpu' | 'cpu' | 'unresolved';
type AutomaticEngine = { status: 'installed' | 'install'; pluginName: string; variantId: string; gpuBudgetEligible: boolean; executionTarget: EngineExecutionTarget } | { status: 'none' };

type EngineOptionStatus = 'installed' | 'recommended' | 'available' | 'warning' | 'unavailable';

interface EngineOption {
    pluginName: string;
    status: EngineOptionStatus;
    reason: string | null;
    engine: AutomaticEngine;
}

const isSelectableVariant = (option: BackendVariantOptionResponse): boolean => option.id !== AUTO_BACKEND_VARIANT_ID && option.availabilityType === 'available' && option.compatibility?.status !== 'incompatible';

const isWarningVariant = (option: BackendVariantOptionResponse): boolean => option.id !== AUTO_BACKEND_VARIANT_ID && option.availabilityType === 'hardware_warning' && option.compatibility?.status !== 'incompatible';

const hasPotentialGpuVariant = (variants: BackendVariantsResponse): boolean => variants.options.some((option) => option.id !== AUTO_BACKEND_VARIANT_ID && option.id !== CPU_BACKEND_VARIANT_ID && option.availabilityType !== 'unavailable' && option.compatibility?.status !== 'incompatible');

const isCpuVariant = (option: BackendVariantOptionResponse | undefined): boolean => option !== undefined && (option.gpuBindingRuntimeFamily === 'none' || option.gpuBindingRuntimeFamily === null) && (option.id === CPU_BACKEND_VARIANT_ID || option.id.startsWith('cpu-'));

const resolveExecutionTarget = (option: BackendVariantOptionResponse | undefined, resolved: boolean): EngineExecutionTarget => {
    if (!resolved || option?.availabilityType !== 'available' || option.compatibility?.status !== 'compatible') return 'unresolved';
    if (isCpuVariant(option)) return 'cpu';
    return option.gpuBindingRuntimeFamily !== null && GPU_RUNTIME_FAMILY_BRANDS.has(option.gpuBindingRuntimeFamily) ? 'gpu' : 'unresolved';
};

const engineGuidance = (candidate: EngineCandidate, engine: AutomaticEngine): string | null => {
    const variants = candidate.variants;
    if (variants === null || engine.status === 'none' || (engine.status === 'installed' && engine.variantId === AUTO_BACKEND_VARIANT_ID)) return null;
    return resolveBackendVariantGuidance({ ...variants, selectedVariantId: engine.variantId });
};

const describeEngine = (candidate: EngineCandidate, hasGpu: boolean): AutomaticEngine => {
    const variants = candidate.variants;
    const installedVariantId = variants?.installedVariantId ?? null;
    const installedOption = variants?.options.find((option) => option.id === installedVariantId);
    if (installedVariantId !== null && candidate.operational && installedOption?.compatibility?.status !== 'incompatible') {
        return { status: 'installed', pluginName: candidate.pluginName, variantId: installedVariantId, gpuBudgetEligible: hasGpu && installedVariantId !== CPU_BACKEND_VARIANT_ID && !isCpuVariant(installedOption), executionTarget: resolveExecutionTarget(installedOption, variants?.installedVariantResolution === 'resolved') };
    }
    if (variants === null || !variants.options.some(isSelectableVariant)) {
        return { status: 'none' };
    }
    return { status: 'install', pluginName: candidate.pluginName, variantId: AUTO_BACKEND_VARIANT_ID, gpuBudgetEligible: hasGpu && hasPotentialGpuVariant(variants), executionTarget: 'unresolved' };
};

const orderCandidates = (candidates: readonly EngineCandidate[]): EngineCandidate[] => AUTOMATIC_ENGINE_ORDER.flatMap((pluginName) => candidates.filter((candidate) => candidate.pluginName === pluginName));

const resolveAutomaticEngine = (candidates: readonly EngineCandidate[], hasGpu: boolean): AutomaticEngine => {
    const described = orderCandidates(candidates).map((candidate) => describeEngine(candidate, hasGpu));
    return described.find((engine) => engine.status === 'installed') ?? described.find((engine) => engine.status === 'install') ?? { status: 'none' };
};

const matchesHostGpu = (option: BackendVariantOptionResponse, gpuBrands: readonly HardwareBrand[]): boolean => {
    const familyBrands = option.gpuBindingRuntimeFamily === null ? undefined : GPU_RUNTIME_FAMILY_BRANDS.get(option.gpuBindingRuntimeFamily);
    return familyBrands !== undefined && gpuBrands.some((brand) => familyBrands.includes(brand));
};

const describeWarningEngine = (candidate: EngineCandidate, gpuBrands: readonly HardwareBrand[]): EngineOption => {
    if (candidate.rejection?.type === 'plugin_incompatible') return { pluginName: candidate.pluginName, status: 'unavailable', reason: candidate.rejection.message, engine: { status: 'none' } };
    const variants = candidate.variants;
    const warningOptions = variants?.options.filter(isWarningVariant) ?? [];
    const warning = warningOptions.find((option) => matchesHostGpu(option, gpuBrands)) ?? warningOptions.find((option) => option.id === CPU_BACKEND_VARIANT_ID) ?? null;
    if (warning === null || variants === null) {
        const reason = (candidate.variants ? resolveBackendVariantGuidance(candidate.variants) : null) ?? candidate.variants?.options.find((option) => option.unavailableReason !== null)?.unavailableReason ?? null;
        return { pluginName: candidate.pluginName, status: 'unavailable', reason, engine: { status: 'none' } };
    }
    return { pluginName: candidate.pluginName, status: 'warning', reason: resolveBackendVariantGuidance({ ...variants, selectedVariantId: warning.id }) ?? warning.unavailableReason, engine: { status: 'install', pluginName: candidate.pluginName, variantId: candidate.pluginName === 'vllm' ? AUTO_BACKEND_VARIANT_ID : warning.id, gpuBudgetEligible: !isCpuVariant(warning), executionTarget: 'unresolved' } };
};

const describeEngineOptions = (candidates: readonly EngineCandidate[], gpuBrands: readonly HardwareBrand[], automatic: AutomaticEngine): EngineOption[] =>
    orderCandidates(candidates).map((candidate) => {
        const engine = describeEngine(candidate, gpuBrands.length > 0);
        if (engine.status === 'installed') return { pluginName: candidate.pluginName, status: 'installed', reason: engineGuidance(candidate, engine), engine };
        if (engine.status === 'install') {
            const recommended = automatic.status === 'install' && automatic.pluginName === candidate.pluginName;
            return { pluginName: candidate.pluginName, status: recommended ? 'recommended' : 'available', reason: engineGuidance(candidate, engine), engine };
        }
        return describeWarningEngine(candidate, gpuBrands);
    });

export { AUTOMATIC_ENGINE_ORDER, describeEngineOptions, resolveAutomaticEngine };
export type { AutomaticEngine, EngineCandidate, EngineOption, EngineOptionStatus };
