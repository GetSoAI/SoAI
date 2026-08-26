/* SoAI - Shared frontend API types plugins [frontend/assets/ts/core/api/types/plugins.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ProviderAddOptions {
    apiUrl: string;
    apiKey?: string;
    name?: string;
    modelsFilter?: string | string[] | Iterable<string>;
}

interface ProviderUpdateOptions {
    name?: string;
    apiKey?: string;
    modelsFilter?: string | string[] | Iterable<string>;
}

interface SearchModelsOptions {
    limit?: number;
    signal?: AbortSignal;
}

export type { ProviderAddOptions, ProviderUpdateOptions, SearchModelsOptions };
