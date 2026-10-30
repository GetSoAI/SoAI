/* SoAI - Immutable drawing records and capacity outcomes [frontend/assets/ts/core/drawing/drawingRecords.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type DrawingPoint = Readonly<{ x: number; y: number }>;
type DrawingStrokeOperation<TTool extends string> = Readonly<{
    type: 'stroke';
    tool: TTool;
    color: string;
    width: number;
    points: readonly DrawingPoint[];
}>;
type DrawingShapeOperation<TShape extends string> = Readonly<{
    type: 'shape';
    shape: TShape;
    color: string;
    width: number;
    start: DrawingPoint;
    end: DrawingPoint;
}>;
type DrawingDrawOperation<TTool extends string, TShape extends string> = DrawingStrokeOperation<TTool> | DrawingShapeOperation<TShape>;
type DrawingOperation<TTool extends string, TShape extends string> = DrawingDrawOperation<TTool, TShape> | Readonly<{ type: 'clear' }>;
type DrawingLimits = Readonly<{ retainedOperations: number; retainedPoints: number; gesturePoints: number }>;
type DrawingCapacityResult = Readonly<{ type: 'available' }> | Readonly<{ type: 'capacity-rejected'; limit: keyof DrawingLimits }>;
type DrawingMutationResult = Readonly<{ type: 'applied' }> | Readonly<{ type: 'no-op' }> | Extract<DrawingCapacityResult, { type: 'capacity-rejected' }>;

export type { DrawingCapacityResult, DrawingDrawOperation, DrawingLimits, DrawingMutationResult, DrawingOperation, DrawingPoint, DrawingShapeOperation, DrawingStrokeOperation };
