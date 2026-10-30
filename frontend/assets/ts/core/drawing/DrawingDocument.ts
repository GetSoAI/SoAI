/* SoAI - Bounded immutable drawing history [frontend/assets/ts/core/drawing/DrawingDocument.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isNonNegativeInteger, isPositiveInteger } from '@core/typeGuards.ts';
import type { DrawingCapacityResult, DrawingDrawOperation, DrawingLimits, DrawingMutationResult, DrawingOperation, DrawingPoint } from '@core/drawing/drawingRecords.ts';

const requirePoint = (point: DrawingPoint): void => {
    if (!isFiniteNumber(point.x) || !isFiniteNumber(point.y)) throw new Error('Drawing geometry must be finite');
};

const operationPoints = <TTool extends string, TShape extends string>(operation: DrawingOperation<TTool, TShape>): number => (operation.type === 'clear' ? 0 : operation.type === 'shape' ? 2 : operation.points.length);

class DrawingDocument<TTool extends string, TShape extends string> {
    readonly #limits: DrawingLimits;
    readonly #applied: DrawingOperation<TTool, TShape>[] = [];
    readonly #undone: DrawingOperation<TTool, TShape>[] = [];
    #appliedPoints = 0;
    #undonePoints = 0;

    constructor(limits: DrawingLimits) {
        if (!isPositiveInteger(limits.retainedOperations) || !isPositiveInteger(limits.retainedPoints) || !isPositiveInteger(limits.gesturePoints)) throw new Error('Drawing limits must be positive integers');
        this.#limits = Object.freeze({ ...limits });
    }

    capacity(points: number, type: 'stroke' | 'shape' | 'clear'): DrawingCapacityResult {
        if (!isNonNegativeInteger(points)) throw new Error('Drawing point count must be a nonnegative integer');
        if (type === 'stroke' && points > this.#limits.gesturePoints) return { type: 'capacity-rejected', limit: 'gesturePoints' };
        if (this.#applied.length + 1 > this.#limits.retainedOperations) return { type: 'capacity-rejected', limit: 'retainedOperations' };
        if (this.#appliedPoints + points > this.#limits.retainedPoints) return { type: 'capacity-rejected', limit: 'retainedPoints' };
        return { type: 'available' };
    }

    commit(operation: DrawingDrawOperation<TTool, TShape>): DrawingMutationResult {
        const count = operationPoints(operation);
        if (operation.type === 'stroke' && count === 0) return { type: 'no-op' };
        const capacity = this.capacity(count, operation.type);
        if (capacity.type === 'capacity-rejected') return capacity;
        if (!isFiniteNumber(operation.width) || operation.width <= 0) throw new Error('Drawing width must be positive and finite');
        if (operation.type === 'stroke') {
            for (const point of operation.points) requirePoint(point);
            this.#accept(Object.freeze({ ...operation, points: Object.freeze(operation.points.map((point) => Object.freeze({ ...point }))) }));
        } else {
            requirePoint(operation.start);
            requirePoint(operation.end);
            this.#accept(Object.freeze({ ...operation, start: Object.freeze({ ...operation.start }), end: Object.freeze({ ...operation.end }) }));
        }
        return { type: 'applied' };
    }

    clear(): DrawingMutationResult {
        if (!this.hasContent()) return { type: 'no-op' };
        const capacity = this.capacity(0, 'clear');
        if (capacity.type === 'capacity-rejected') return capacity;
        this.#accept(Object.freeze({ type: 'clear' }));
        return { type: 'applied' };
    }

    undo(): DrawingMutationResult {
        const operation = this.#applied.pop();
        if (operation === undefined) return { type: 'no-op' };
        this.#undone.push(operation);
        const points = operationPoints(operation);
        this.#appliedPoints -= points;
        this.#undonePoints += points;
        return { type: 'applied' };
    }

    redo(): DrawingMutationResult {
        const operation = this.#undone.pop();
        if (operation === undefined) return { type: 'no-op' };
        this.#applied.push(operation);
        const points = operationPoints(operation);
        this.#appliedPoints += points;
        this.#undonePoints -= points;
        return { type: 'applied' };
    }

    retainedUsage(): Readonly<{ operations: number; points: number }> {
        return Object.freeze({ operations: this.#applied.length + this.#undone.length, points: this.#appliedPoints + this.#undonePoints });
    }

    canUndo(): boolean {
        return this.#applied.length > 0;
    }
    canRedo(): boolean {
        return this.#undone.length > 0;
    }
    hasContent(): boolean {
        const last = this.#applied[this.#applied.length - 1];
        return last !== undefined && last.type !== 'clear';
    }

    visibleOperations(): readonly DrawingDrawOperation<TTool, TShape>[] {
        const visible: DrawingDrawOperation<TTool, TShape>[] = [];
        for (const operation of this.#applied) {
            if (operation.type === 'clear') visible.length = 0;
            else visible.push(operation);
        }
        return Object.freeze(visible);
    }

    #accept(operation: DrawingOperation<TTool, TShape>): void {
        this.#applied.push(operation);
        this.#appliedPoints += operationPoints(operation);
        this.#undone.length = 0;
        this.#undonePoints = 0;
    }
}

export { DrawingDocument };
