/* SoAI - Wizard AI setup model catalog matching [frontend/assets/ts/pages/wizard/services/aisetup/catalog/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DownloadParameters } from '@core/modelactions/contracts.ts';
import { findModelCatalogEntry } from '@pages/wizard/services/aisetup/catalog/constants.ts';
import { isChatSelectableModel } from '@core/models/chatModelAvailability.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { AiSetupModel, AiSetupProvider, AiSetupState } from '@core/storage/aisetup/aiSetupTypes.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import type { ModelData } from '@core/types/modelTypes.ts';

const OLLAMA_PLUGIN_NAME = 'ollama';
const GGUF_FILE_SUFFIX = '.gguf';
const GGUF_SHARD_PATTERN = /^(.+?)-\d{5}-of-\d{5}\.gguf$/iu;
const REVISION_PATH_SEPARATOR = '//';
const REVISION_TOKEN_PATTERN = /^@[^/]+$/u;
const DEFAULT_REVISION_TOKENS = new Set(['', 'default', 'main', 'master']);

const sanitizeSegment = (value: string): string =>
    value
        .trim()
        .replace(/[^A-Za-z0-9._-]+/gu, '_')
        .replace(/^[._-]+|[._-]+$/gu, '');

const buildGgufArtifactName = (name: string): string => {
    const trimmed = name.trim();
    const stem = GGUF_SHARD_PATTERN.exec(trimmed)?.[1] ?? (trimmed.toLowerCase().endsWith(GGUF_FILE_SUFFIX) ? trimmed.slice(0, -GGUF_FILE_SUFFIX.length) : trimmed);
    return `${sanitizeSegment(stem) || 'model'}${GGUF_FILE_SUFFIX}`;
};

const normalizeRevision = (value: string): string => {
    const token = sanitizeSegment(value).toLowerCase();
    return DEFAULT_REVISION_TOKENS.has(token) ? '' : token;
};

const splitArtifactReference = (reference: string): { revision: string; path: string } => {
    const separator = reference.indexOf(REVISION_PATH_SEPARATOR);
    return separator < 0 ? { revision: '', path: reference } : { revision: normalizeRevision(reference.slice(0, separator)), path: reference.slice(separator + REVISION_PATH_SEPARATOR.length) };
};

const readModelRevision = (model: ModelData, identifierRevision: string | null): string | null => (model.requestedRevision === undefined ? identifierRevision : normalizeRevision(model.requestedRevision));

const matchesGgufArtifact = (model: ModelData, sourceModelId: string, repositoryId: string, artifactName: string, revision: string): boolean => {
    const repository = repositoryId
        .split('/')
        .filter(Boolean)
        .map((segment) => sanitizeSegment(segment) || 'default')
        .join('/')
        .toLowerCase();
    const artifact = `/${buildGgufArtifactName(artifactName)}`.toLowerCase();
    if (!sourceModelId.startsWith(repository) || !sourceModelId.endsWith(artifact)) return false;
    const token = sourceModelId.slice(repository.length, sourceModelId.length - artifact.length);
    return (token === '' || REVISION_TOKEN_PATTERN.test(token)) && readModelRevision(model, normalizeRevision(token.slice(1))) === revision;
};

const matchesArtifactSource = (model: ModelData, sourceModelId: string, item: AiSetupModel & { repositoryId: string; artifactReference: string }): boolean => {
    const candidate = sourceModelId.toLowerCase();
    if (item.pluginName === OLLAMA_PLUGIN_NAME) return candidate === (item.repositoryId.includes(':') ? item.repositoryId : `${item.repositoryId}:${item.artifactReference}`).toLowerCase();
    const { revision, path } = splitArtifactReference(item.artifactReference);
    if (path.toLowerCase().endsWith(GGUF_FILE_SUFFIX)) return matchesGgufArtifact(model, candidate, item.repositoryId, item.artifactName ?? path.split('/').at(-1) ?? path, revision);
    return candidate === (item.repositoryId.split('/').at(-1) ?? item.repositoryId).toLowerCase() && model.repositoryId?.toLowerCase() === item.repositoryId.toLowerCase() && readModelRevision(model, null) === normalizeRevision(item.artifactReference);
};

const findDownloadedModel = (models: readonly ModelData[], item: AiSetupModel): ModelData | null => {
    const { repositoryId, artifactReference } = item;
    if (repositoryId === null || artifactReference === null) return null;
    return models.find((model) => model.plugin === item.pluginName && isString(model.sourceModelId) && matchesArtifactSource(model, model.sourceModelId, { ...item, repositoryId, artifactReference })) ?? null;
};

const findItemModel = (models: readonly ModelData[], item: AiSetupModel): ModelData | null => {
    if (item.modelId !== null) return models.find((model) => readModelOperationId(model) === item.modelId || model.id === item.modelId) ?? null;
    return item.source === 'local' ? findDownloadedModel(models, item) : null;
};

const readModelOperationId = (model: ModelData): string => toTrimmedString(model.universalId) || model.id;

const listProviderModels = (models: readonly ModelData[], provider: AiSetupProvider): ModelData[] => models.filter((model) => model.plugin === provider.pluginName && model.providerId === provider.providerId && isChatSelectableModel(model));

const readConfigurationFingerprint = (model: ModelData): string | null => (isFiniteNumber(model.parameterVersion) ? String(model.parameterVersion) : null);

const readModelLabel = (model: ModelData | null, fallback: string): string => model?.displayName || model?.name || fallback;

export { findDownloadedModel, findItemModel, listProviderModels, readConfigurationFingerprint, readModelLabel, readModelOperationId };

const readAiSetupDownloadRequest = (setup: AiSetupState, item: AiSetupModel): DownloadParameters | null => {
    if (item.repositoryId === null || item.artifactReference === null) return null;
    return {
        wizard: { previousTaskId: setup.lastLocalDownloadTaskId },
        plugin: item.pluginName,
        modelId: item.repositoryId,
        quantization: item.artifactReference,
        displayName: findModelCatalogEntry(item.catalogId)?.name ?? item.artifactName ?? item.artifactReference
    };
};

export { readAiSetupDownloadRequest };
