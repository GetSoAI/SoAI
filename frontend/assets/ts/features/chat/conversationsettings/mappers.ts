/* SoAI - Chat feature conversation settings mapping [frontend/assets/ts/features/chat/conversationsettings/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import { toTrimmedStringOrNull, uniqueSortedStrings } from '@core/normalize.ts';
import { supportsOpenAIEndpointForEntry } from '@core/openai/capabilityChecks.ts';
import type { ModelData } from '@core/types/modelTypes.ts';

const isEmbeddingCapable = (entry: ModelData): boolean => supportsOpenAIEndpointForEntry(entry, 'embeddings');

const resolveEmbeddingModelsFromStream = (models: readonly ModelData[] | null | undefined): string[] => {
    if (!models) {
        return [];
    }
    const resolved = models
        .filter((entry) => isEmbeddingCapable(entry))
        .map((entry) => {
            return toTrimmedStringOrNull(entry['id']) ?? toTrimmedStringOrNull(entry.universalId) ?? toTrimmedStringOrNull(entry['name']);
        })
        .filter((value): value is string => value !== null);
    return uniqueSortedStrings(resolved, getCurrentLocale());
};

export { resolveEmbeddingModelsFromStream };
