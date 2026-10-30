/* SoAI - Chat sketch modal contracts [frontend/assets/ts/pages/chat/controllers/modals/sketch/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DrawingCapacityResult } from '@core/drawing/drawingRecords.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatSketchDrawOperation, ChatSketchToolType } from '@features/chat/public.ts';

interface ChatSketchModalRefs {
    modal: HTMLElement;
    status: HTMLElement;
    canvas: HTMLCanvasElement;
    tools: readonly HTMLButtonElement[];
    swatches: readonly HTMLButtonElement[];
    color: HTMLInputElement;
    size: HTMLInputElement;
    sizeValue: HTMLOutputElement;
    undo: HTMLButtonElement;
    redo: HTMLButtonElement;
    clear: HTMLButtonElement;
    attach: HTMLButtonElement;
    stage: HTMLElement;
    grip: HTMLButtonElement;
    sizePreview: HTMLElement;
}

interface ChatSketchModalHost {
    feedback: Pick<PageFeedback, 'handle' | 'show'>;
    presenter: ModalPresenterApi;
    submit(file: File): void | Promise<void>;
}

type ChatSketchStyle = Readonly<{
    tool: ChatSketchToolType;
    color: string;
    width: number;
}>;

interface ChatSketchPointerInputHost {
    canvas: HTMLCanvasElement;
    signal: AbortSignal;
    isEnabled(): boolean;
    resolveStyle(): ChatSketchStyle;
    capacity(points: number, type: 'stroke' | 'shape'): DrawingCapacityResult;
    onCapacityRejected(): void;
    onPreview(operation: ChatSketchDrawOperation | null): void;
    onCommit(operation: ChatSketchDrawOperation): void;
    onCancel(): void;
}

type ChatSketchResizeTarget = Readonly<{
    displayWidth: number;
    sheetWidth: number;
    sheetHeight: number;
}>;

interface ChatSketchResizeHost {
    stage: HTMLElement;
    canvas: HTMLCanvasElement;
    grip: HTMLButtonElement;
    signal: AbortSignal;
    isEnabled(): boolean;
    onResize(target: ChatSketchResizeTarget): void;
}

export type { ChatSketchModalHost, ChatSketchModalRefs, ChatSketchPointerInputHost, ChatSketchResizeHost, ChatSketchResizeTarget, ChatSketchStyle };
