/* SoAI - Shared operation progress contracts [frontend/assets/ts/core/operationprogress/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface OperationProgressReporter {
    update(key: string, data: OperationProgressData): void;
    remove(key: string): void;
    clear(): void;
    destroy(): void;
    hasActiveOperations(): boolean;
}

interface OperationProgressCancelContext {
    button: HTMLButtonElement;
    element: HTMLElement;
    reporter: OperationProgressReporter;
}

interface OperationProgressOptions {
    showCancel?: boolean;
    showBadge?: boolean;
    cancelSelector?: string | null;
    onCancel?: ((key: string, context: OperationProgressCancelContext) => void | Promise<void>) | null;
    backgroundButtonId?: string | null;
    extraClassName?: string | null;
}

interface OperationProgressData {
    progress?: number;
    message?: string;
    badge?: string;
    details?: string;
    state?: 'success' | 'error' | 'downloading' | 'pending' | 'info';
    cancelable?: boolean;
}

export type { OperationProgressCancelContext, OperationProgressData, OperationProgressOptions, OperationProgressReporter };
