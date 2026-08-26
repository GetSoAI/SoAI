/* SoAI - Prompts page prompt enhancer contracts [frontend/assets/ts/pages/prompts/controllers/promptenhancer/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiModelCatalogResponse } from '@core/openai/modelCatalog.ts';
import type { PromptRequest } from '@core/api/contracts/promptContracts.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import type { SyntaxHighlighterInterface } from '@pages/prompts/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface PromptEnhancerSourceSnapshot {
    id: string;
    name: string;
    content: string;
    color: string | null;
    modifiedAtMs: number;
}

interface PromptEnhancerModelCatalogState {
    status: 'idle' | 'ready' | 'error' | 'unavailable';
    availableModelIds: Set<string>;
}

interface PromptEnhancerRunState {
    source: PromptEnhancerSourceSnapshot | null;
    modelId: string | null;
    status: 'idle' | 'streaming' | 'success' | 'error' | 'aborted';
    output: string;
    statusMessage: string;
    errorMessage: string | null;
    detectedLanguage: string | null;
    abortController: AbortController | null;
    showWaitMessage: boolean;
    showOriginal: boolean;
    compareSideBySide: boolean;
    modelHelpMessage: string | null;
}

interface PromptEnhancerHost extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    modals: ModalPresenterApi;
    findPromptById(id: string | number): PromptRecord | null;
    upsertPromptRecord(record: PromptRecord): PromptRecord;
    createPrompt(payload: PromptRequest): Promise<PromptRecord>;
    updatePrompt(id: string | number, payload: PromptRequest): Promise<PromptRecord>;
    runTask<T>(name: string, task: () => Promise<T>, options?: Record<string, JsonValue>): Promise<T | null>;
    fetchModelCatalog(): Promise<OpenAiModelCatalogResponse | null>;
    getPromptEnhancerModel(): string | null;
    setPromptEnhancerModel(value: string | null): void;
    downloadTextFile(content: string, filename: string, mimeType?: string): void;
    copyPromptContent(content: string | null): Promise<void>;
    buildPromptFilename(name: string): string;
    closePromptView(): void;
    getViewedPromptId(): string | number | null;
}

interface PromptEnhancerDependencies {
    host: PromptEnhancerHost;
    syntaxHighlighter: SyntaxHighlighterInterface;
    resources: ResourceTracker;
}

export type { PromptEnhancerDependencies, PromptEnhancerHost, PromptEnhancerModelCatalogState, PromptEnhancerRunState, PromptEnhancerSourceSnapshot };
