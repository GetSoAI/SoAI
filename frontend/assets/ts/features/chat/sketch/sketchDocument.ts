/* SoAI - Frontend chat sketch operation history [frontend/assets/ts/features/chat/sketch/sketchDocument.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatSketchFreehandToolType, ChatSketchShapeType } from '@features/chat/sketch/sketchCatalog.ts';

type ChatSketchPoint = Readonly<{ x: number; y: number }>;

type ChatSketchStrokeOperation = Readonly<{
    type: 'stroke';
    tool: ChatSketchFreehandToolType;
    color: string;
    width: number;
    points: ReadonlyArray<ChatSketchPoint>;
}>;

type ChatSketchShapeOperation = Readonly<{
    type: 'shape';
    shape: ChatSketchShapeType;
    color: string;
    width: number;
    start: ChatSketchPoint;
    end: ChatSketchPoint;
}>;

type ChatSketchDrawOperation = ChatSketchStrokeOperation | ChatSketchShapeOperation;
type ChatSketchOperation = ChatSketchDrawOperation | Readonly<{ type: 'clear' }>;

class ChatSketchDocument {
    readonly #applied: ChatSketchOperation[] = [];
    readonly #undone: ChatSketchOperation[] = [];

    commit(operation: ChatSketchDrawOperation): void {
        this.#applied.push(operation);
        this.#undone.length = 0;
    }

    clear(): boolean {
        if (!this.hasContent()) return false;
        this.#applied.push({ type: 'clear' });
        this.#undone.length = 0;
        return true;
    }

    undo(): boolean {
        const operation = this.#applied.pop();
        if (operation === undefined) return false;
        this.#undone.push(operation);
        return true;
    }

    redo(): boolean {
        const operation = this.#undone.pop();
        if (operation === undefined) return false;
        this.#applied.push(operation);
        return true;
    }

    canUndo(): boolean {
        return this.#applied.length > 0;
    }

    canRedo(): boolean {
        return this.#undone.length > 0;
    }

    hasContent(): boolean {
        return this.visibleOperations().length > 0;
    }

    visibleOperations(): readonly ChatSketchDrawOperation[] {
        const visible: ChatSketchDrawOperation[] = [];
        for (const operation of this.#applied) {
            if (operation.type === 'clear') {
                visible.length = 0;
                continue;
            }
            visible.push(operation);
        }
        return visible;
    }
}

export { ChatSketchDocument };
export type { ChatSketchDrawOperation, ChatSketchOperation, ChatSketchPoint, ChatSketchShapeOperation, ChatSketchStrokeOperation };
