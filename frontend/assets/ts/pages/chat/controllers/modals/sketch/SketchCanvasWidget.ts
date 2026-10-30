/* SoAI - Chat sketch canvas layers widget [frontend/assets/ts/pages/chat/controllers/modals/sketch/SketchCanvasWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { CHAT_SKETCH_CANVAS_HEIGHT, CHAT_SKETCH_CANVAS_WIDTH, paintChatSketchBackground, paintChatSketchOperation, type ChatSketchDrawOperation } from '@features/chat/public.ts';

const requireCanvasContext = (canvas: HTMLCanvasElement): CanvasRenderingContext2D => {
    const context = canvas.getContext('2d');
    if (context === null) throw new Error('Chat sketch canvas 2D context is unavailable');
    return context;
};

class SketchCanvasWidget {
    readonly #canvas: HTMLCanvasElement;
    readonly #context: CanvasRenderingContext2D;
    readonly #committed: HTMLCanvasElement;
    readonly #committedContext: CanvasRenderingContext2D;
    #preview: ChatSketchDrawOperation | null = null;
    #frame: number | null = null;
    #disposed = false;
    #projected = false;

    constructor(canvas: HTMLCanvasElement) {
        this.#canvas = canvas;
        this.#context = requireCanvasContext(canvas);
        this.#committed = canvas.ownerDocument.createElement('canvas');
        this.#committedContext = requireCanvasContext(this.#committed);
        this.#setSheetSize(CHAT_SKETCH_CANVAS_WIDTH, CHAT_SKETCH_CANVAS_HEIGHT);
        this.#paintLayers([]);
    }

    isProjected(): boolean {
        return this.#projected && !this.#disposed;
    }

    get exportCanvas(): HTMLCanvasElement {
        return this.#committed;
    }

    preview(operation: ChatSketchDrawOperation | null): void {
        this.#preview = operation;
        if (this.#frame !== null || this.#disposed) return;
        this.#frame = getRequestAnimationFrame()(() => {
            this.#frame = null;
            if (!this.#disposed) this.#present();
        });
    }

    commit(operation: ChatSketchDrawOperation): void {
        this.#projected = false;
        paintChatSketchOperation(this.#committedContext, operation);
        this.#preview = null;
        this.#presentNow();
        this.#projected = true;
    }

    rebuild(operations: readonly ChatSketchDrawOperation[]): void {
        this.#paintLayers(operations);
    }

    resize(width: number, height: number, operations: readonly ChatSketchDrawOperation[]): void {
        if (width === this.#canvas.width && height === this.#canvas.height) return;
        this.#setSheetSize(width, height);
        this.#paintLayers(operations);
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#cancelFrame();
        this.#preview = null;
    }

    #setSheetSize(width: number, height: number): void {
        this.#canvas.width = width;
        this.#canvas.height = height;
        this.#committed.width = width;
        this.#committed.height = height;
    }

    #paintLayers(operations: readonly ChatSketchDrawOperation[]): void {
        this.#projected = false;
        paintChatSketchBackground(this.#committedContext);
        for (const operation of operations) paintChatSketchOperation(this.#committedContext, operation);
        this.#preview = null;
        this.#presentNow();
        this.#projected = true;
    }

    #presentNow(): void {
        this.#cancelFrame();
        if (!this.#disposed) this.#present();
    }

    #cancelFrame(): void {
        if (this.#frame === null) return;
        getCancelAnimationFrame()(this.#frame);
        this.#frame = null;
    }

    #present(): void {
        this.#context.drawImage(this.#committed, 0, 0);
        if (this.#preview !== null) paintChatSketchOperation(this.#context, this.#preview);
    }
}

export { SketchCanvasWidget };
