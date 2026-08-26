/* SoAI - Chat model session contracts [frontend/assets/ts/pages/chat/controllers/chatpage/models/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ActiveComparisonRun, ConversationMessage, ConversationProjectionAnalysis, ModelStreamReadiness } from '@features/chat/public.ts';
import type { ChatModelsController } from '@pages/chat/controllers/chatmodelscontroller/ChatModelsController.ts';
import type { ChatModelControlController } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlController.ts';

type ComparisonPresentationState = { isCurrentStreaming: boolean; activeComparisonRun: ActiveComparisonRun | null };

interface ChatModelSessionContract {
    initializeModelControllers(models: ChatModelsController, modelControl: ChatModelControlController): void;
    ensureStream(): Promise<ModelStreamReadiness>;
    resolveKey(candidate: string | null | undefined): string | null;
    displayName(modelId: string | null): string;
    messageSenderLabel(message: ConversationMessage, role: string): string;
    updateUi(root?: Element): void;
    syncHeaderCatalog(root?: Element): void;
    closeControlMenu(): void;
    handleControlAction(actionElement: HTMLElement): void;
    handleControlSearchInput(input: HTMLInputElement): void;
    handleComparisonNavigation(actionElement: HTMLElement): void;
    syncComparisonSelection(analysis: ConversationProjectionAnalysis): ReadonlyMap<number, number>;
    syncComparisonPresentation(container: Element, state: ComparisonPresentationState): void;
    dispose(): void;
}

interface ChatModelSessionHost {
    modelSession: ChatModelSessionContract;
}

export type { ChatModelSessionContract, ChatModelSessionHost, ComparisonPresentationState };
