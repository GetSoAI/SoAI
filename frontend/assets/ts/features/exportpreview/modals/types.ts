/* SoAI - Shared export preview modal types [frontend/assets/ts/features/exportpreview/modals/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ExportPreviewSnapshotPayload } from '@core/api/contracts/exportPreviewContracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface ExportPreviewModalOpenRequest {
    snapshotResource: string;
    payload: JsonObject;
    scope: string;
    boundaryName: string;
    downloadBoundaryName: string;
}

interface ExportPreviewModalState {
    isOpen: boolean;
    scope: string;
    filename: string;
    content: string;
    downloadUrl: string;
    downloadBoundaryName: string;
}

interface ExportPreviewModalHost {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    addClassName(target: Element, className: string): void;
    removeClassName(target: Element, className: string): void;
    updateText(target: Element, text: string): void;
    showNotification(message: string, type: NotificationType): void;
}

interface ExportPreviewModalDependencies {
    host: ExportPreviewModalHost;
}

interface ExportPreviewModalEventBinding {
    modalRoot: HTMLElement;
    signal: AbortSignal;
}

export type { ExportPreviewModalDependencies, ExportPreviewModalEventBinding, ExportPreviewModalHost, ExportPreviewModalOpenRequest, ExportPreviewModalState, ExportPreviewSnapshotPayload };
