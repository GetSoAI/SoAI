/* SoAI - Prompts page types [frontend/assets/ts/pages/prompts/contracts/promptsTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PromptBatchDeleteResponse, PromptRequest, PromptResponse } from '@core/api/contracts/promptContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

export interface PromptsApiClient {
    list: () => Promise<PromptResponse[]>;
    create: (data: PromptRequest) => Promise<PromptResponse>;
    get: (id: string) => Promise<PromptResponse>;
    update: (id: string, data: PromptRequest) => Promise<PromptResponse>;
    delete: (id: string) => Promise<void>;
    batchDelete: (ids: string[]) => Promise<PromptBatchDeleteResponse>;
}

export type DownloadFileFunction = (data: Blob | string, filename: string, mimeType?: string) => void;

export interface UIElements {
    container?: HTMLElement | null;
    list?: HTMLElement | null;
    header?: HTMLElement | null;
    stats?: HTMLElement | null;
    emptyState?: HTMLElement | null;
    loadingSpinner?: HTMLElement | null;
    errorDisplay?: HTMLElement | null;
    searchInput?: HTMLInputElement | null;
    filterDropdown?: HTMLSelectElement | null;
    sortDropdown?: HTMLSelectElement | null;
    groupDropdown?: HTMLSelectElement | null;
    bulkActions?: HTMLElement | null;
    [key: string]: HTMLElement | HTMLInputElement | HTMLSelectElement | null | undefined;
}

export interface CollectionLayoutConfig {
    groupBy?: string;
    sortBy?: string;
    filterBy?: string;
    [key: string]: JsonValue | undefined;
}
