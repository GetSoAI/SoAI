/* SoAI - Models feature rename modal contracts [frontend/assets/ts/features/models/modals/renamemodal/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface RenameFormResetHost {
    optionalHTMLElement(selector: string, context?: Element): HTMLElement | null;
    setUIValue(target: Element, value: string, options?: { attribute?: string; skipChangeEvent?: boolean }, context?: Element): void;
}

interface RenameModelModalState {
    selectedModel: ModelRecord | null;
    originalAlias: string;
}

interface RenameModelActions {
    updateAlias: (universalId: string, payload: { displayName: string; description: string | null }) => Promise<SuccessfulMutationResponse>;
    removeAlias: (universalId: string) => Promise<SuccessfulMutationResponse>;
}

interface RenameModelModalHost extends RenameFormResetHost {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    showNotification(message: string, type: NotificationType, duration?: number): void;
    runWithBoundary<T>(operation: string, task: () => Promise<T>): Promise<T>;
    updateText(element: Element, text: string): void;
    refreshModelsCollection(): Promise<void>;
    modelActions: RenameModelActions;
}

interface RenameModelModalManagerDependencies {
    host: RenameModelModalHost;
}

export type { RenameFormResetHost, RenameModelActions, RenameModelModalHost, RenameModelModalManagerDependencies, RenameModelModalState };
