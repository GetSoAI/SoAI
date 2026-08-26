/* SoAI - Messaging execution model option mapping [frontend/assets/ts/features/settings/messaging/modelOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isLocalModelCatalogEntry, type LocalModelCatalogEntry, type ModelCatalogEntry, type ModelCatalogResponse } from '@core/api/contracts/modelCatalogContracts.ts';
import { intersectSupportedReasoningLevels, parseSupportedReasoningLevels, type ReasoningEffortLevel } from '@core/chat/parameters/reasoningEffort.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import { resolveModelDisplayName, resolveOpenAiEndpointModelId } from '@core/models/modelIdentity.ts';
import { supportsOpenAIEndpointForEntry } from '@core/openai/capabilityChecks.ts';
import { cloneJsonObject } from '@core/primitives/clone.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import type { MessagingModelOption } from '@features/settings/messaging/types.ts';

interface MessagingModelCandidate {
    entry: ModelCatalogEntry;
    executionId: string;
    displayName: string;
    selectable: boolean;
    supportedReasoningLevels: readonly ReasoningEffortLevel[] | null;
}

type LocalModelsByUniversalId = ReadonlyMap<string, readonly LocalModelCatalogEntry[]>;

const toModelData = (entry: ModelCatalogEntry): ModelData => {
    if (!isLocalModelCatalogEntry(entry)) {
        return {
            id: entry.id,
            name: entry.name,
            type: entry.type,
            loaded: false,
            available: entry.isEnabled,
            isEnabled: entry.isEnabled,
            modalities: [...entry.modalities],
            ...(entry.openaiCapabilities ? { openaiCapabilities: entry.openaiCapabilities } : {}),
            ...(entry.contextWindowTokens === null ? {} : { contextWindowTokens: entry.contextWindowTokens })
        };
    }
    return {
        id: entry.id,
        name: entry.name,
        universalId: entry.universalId,
        modelId: entry.modelId,
        sourceModelId: entry.sourceModelId,
        ...(entry.rawUpstreamModelId === null ? {} : { rawUpstreamModelId: entry.rawUpstreamModelId }),
        type: entry.type,
        plugin: entry.plugin,
        displayName: entry.name,
        hasAlias: entry.hasAlias,
        loaded: entry.isLoaded,
        available: entry.isAvailable,
        isLoaded: entry.isLoaded,
        isAvailable: entry.isAvailable,
        isEnabled: entry.isEnabled,
        isOrphaned: entry.isOrphaned,
        status: entry.status,
        modalities: [...entry.modalities],
        ...(entry.openaiCapabilities ? { openaiCapabilities: entry.openaiCapabilities } : {}),
        ...(entry.contextWindowTokens === null ? {} : { contextWindowTokens: entry.contextWindowTokens })
    };
};

const isEligibleCandidate = (entry: ModelCatalogEntry, model: ModelData): boolean => {
    if (!isLocalModelCatalogEntry(entry)) {
        if (!entry.isEnabled) return false;
    } else if (entry.status.toLowerCase() !== 'active' || !entry.isEnabled || entry.isOrphaned) {
        return false;
    }
    return isChatSelectableModel(model) && supportsOpenAIEndpointForEntry(model, 'chat_completions');
};

const resolveEntryReasoningLevels = (entry: ModelCatalogEntry, localModelsByUniversalId: LocalModelsByUniversalId): readonly ReasoningEffortLevel[] | null => {
    if (isLocalModelCatalogEntry(entry)) return parseSupportedReasoningLevels(entry.openaiCapabilities);
    const constituentIds = [...new Set(entry.models.map((constituent) => constituent.universalId))];
    const constituentLevels: (readonly ReasoningEffortLevel[] | null)[] = [];
    for (const universalId of constituentIds) {
        const matches = localModelsByUniversalId.get(universalId);
        if (!matches || matches.length !== 1) return null;
        const constituent = matches[0];
        if (!constituent) return null;
        constituentLevels.push(parseSupportedReasoningLevels(constituent.openaiCapabilities));
    }
    return intersectSupportedReasoningLevels(constituentLevels);
};

const createCandidate = (entry: ModelCatalogEntry, localModelsByUniversalId: LocalModelsByUniversalId): MessagingModelCandidate | null => {
    const model = toModelData(entry);
    const executionId = resolveOpenAiEndpointModelId(model);
    if (!executionId) return null;
    return {
        entry,
        executionId,
        displayName: resolveModelDisplayName(model) || executionId,
        selectable: isEligibleCandidate(entry, model),
        supportedReasoningLevels: resolveEntryReasoningLevels(entry, localModelsByUniversalId)
    };
};

const resolveCommonValue = <T>(values: readonly T[]): T | null => {
    const first = values[0];
    if (first === undefined || !values.every((value) => deepEqual(value, first))) return null;
    return first;
};

const buildOption = (candidates: readonly MessagingModelCandidate[], identityMatches: readonly ModelCatalogEntry[]): MessagingModelOption => {
    const first = candidates[0];
    if (!first) throw new Error('Messaging model option requires at least one candidate');
    const commonDisplayName = resolveCommonValue(candidates.map((candidate) => candidate.displayName));
    const commonCapabilities = resolveCommonValue(candidates.map((candidate) => candidate.entry.openaiCapabilities));
    const onlyIdentityMatch = identityMatches.length === 1 ? identityMatches[0] : null;
    const detailUniversalId = onlyIdentityMatch && isLocalModelCatalogEntry(onlyIdentityMatch) ? onlyIdentityMatch.universalId : null;
    return Object.freeze({
        executionId: first.executionId,
        detailUniversalId,
        displayName: commonDisplayName ?? first.executionId,
        contextWindowTokens: resolveCommonValue(candidates.map((candidate) => candidate.entry.contextWindowTokens)),
        openaiCapabilities: commonCapabilities ? cloneJsonObject(commonCapabilities) : null,
        supportedReasoningLevels: intersectSupportedReasoningLevels(candidates.map((candidate) => candidate.supportedReasoningLevels))
    });
};

const buildMessagingModelOptions = (catalog: ModelCatalogResponse): readonly MessagingModelOption[] => {
    const candidatesByExecutionId = new Map<string, MessagingModelCandidate[]>();
    const identityMatchesByExecutionId = new Map<string, ModelCatalogEntry[]>();
    const localModelsByUniversalId = new Map<string, LocalModelCatalogEntry[]>();
    for (const entries of Object.values(catalog)) {
        for (const entry of entries) {
            if (!isLocalModelCatalogEntry(entry)) continue;
            const matches = localModelsByUniversalId.get(entry.universalId);
            if (matches) matches.push(entry);
            else localModelsByUniversalId.set(entry.universalId, [entry]);
        }
    }
    for (const entries of Object.values(catalog)) {
        for (const entry of entries) {
            const candidate = createCandidate(entry, localModelsByUniversalId);
            if (!candidate) continue;
            const identityMatches = identityMatchesByExecutionId.get(candidate.executionId);
            if (identityMatches) identityMatches.push(entry);
            else identityMatchesByExecutionId.set(candidate.executionId, [entry]);
            if (!candidate.selectable) continue;
            const current = candidatesByExecutionId.get(candidate.executionId);
            if (current) current.push(candidate);
            else candidatesByExecutionId.set(candidate.executionId, [candidate]);
        }
    }
    const locale = getCurrentLocale();
    return Object.freeze([...candidatesByExecutionId.values()].map((candidates) => buildOption(candidates, identityMatchesByExecutionId.get(candidates[0]?.executionId ?? '') ?? [])).sort((left, right) => left.displayName.localeCompare(right.displayName, locale) || left.executionId.localeCompare(right.executionId, 'en')));
};

const resolveMessagingModelOption = (models: readonly MessagingModelOption[], executionId: string | null | undefined): MessagingModelOption | null => models.find((model) => model.executionId === executionId) ?? null;

export { buildMessagingModelOptions, resolveMessagingModelOption };
