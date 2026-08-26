/* SoAI - Shared OpenAI model catalog [frontend/assets/ts/core/openai/modelCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiModelCatalogEntry, OpenAiModelCatalogResponse } from '@core/api/contracts/openAiModelCatalogContracts.ts';
import { supportsOpenAIEndpointForEntry } from '@core/openai/capabilityChecks.ts';

const hasChatCompletionsCapability = (entry: OpenAiModelCatalogEntry): boolean => {
    return supportsOpenAIEndpointForEntry(entry, 'chat_completions');
};

const sortOpenAiModelCatalogEntries = (entries: OpenAiModelCatalogEntry[]): OpenAiModelCatalogEntry[] => {
    return [...entries].sort((left, right) => left.id.localeCompare(right.id, 'en'));
};

const listOpenAiModelCatalogIds = (catalog: OpenAiModelCatalogResponse): string[] => sortOpenAiModelCatalogEntries(catalog.data).map((entry) => entry.id);

const listOpenAiChatCompletionModels = (catalog: OpenAiModelCatalogResponse): OpenAiModelCatalogEntry[] => sortOpenAiModelCatalogEntries(catalog.data).filter((entry) => hasChatCompletionsCapability(entry));

export { listOpenAiChatCompletionModels, listOpenAiModelCatalogIds, sortOpenAiModelCatalogEntries };
export type { OpenAiModelCatalogEntry, OpenAiModelCatalogResponse };
