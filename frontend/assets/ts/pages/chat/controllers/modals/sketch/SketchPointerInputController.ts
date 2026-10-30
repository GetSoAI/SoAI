/* SoAI - Chat sketch pointer input controller [frontend/assets/ts/pages/chat/controllers/modals/sketch/SketchPointerInputController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { measureViewportBox, measureViewportPoint, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isChatSketchShapeType, type ChatSketchDrawOperation, type ChatSketchPoint } from '@features/chat/public.ts';
import type { ChatSketchPointerInputHost, ChatSketchStyle } from '@pages/chat/controllers/modals/sketch/types.ts';

type ActiveGesture = {
    pointerId: number;
    style: ChatSketchStyle;
    points: ChatSketchPoint[];
};

const MIN_SHAPE_EXTENT = 1;

class SketchPointerInputController {
    readonly #host: ChatSketchPointerInputHost;
    #gesture: ActiveGesture | null = null;

    constructor(host: ChatSketchPointerInputHost) {
        this.#host = host;
        const listener = (event: Event): void => {
            if (event instanceof PointerEvent) this.#handlePointer(event);
        };
        bindEventGroup(
            [
                { target: host.canvas, type: 'pointerdown', listener },
                { target: host.canvas, type: 'pointermove', listener },
                { target: host.canvas, type: 'pointerup', listener },
                { target: host.canvas, type: 'pointercancel', listener },
                { target: host.canvas, type: 'lostpointercapture', listener }
            ],
            host.signal
        );
    }

    isDrawing(): boolean {
        return this.#gesture !== null;
    }

    dispose(): void {
        const gesture = this.#gesture;
        if (gesture === null) return;
        this.#gesture = null;
        this.#release(gesture);
        this.#host.onCancel();
    }

    #release(gesture: ActiveGesture): void {
        if (this.#host.canvas.hasPointerCapture(gesture.pointerId)) this.#host.canvas.releasePointerCapture(gesture.pointerId);
    }

    #reject(gesture: ActiveGesture): void {
        this.#gesture = null;
        this.#release(gesture);
        this.#host.onCancel();
        this.#host.onCapacityRejected();
    }

    #handlePointer(event: PointerEvent): void {
        if (event.type === 'pointerdown') {
            this.#begin(event);
            return;
        }
        const gesture = this.#gesture;
        if (gesture === null || gesture.pointerId !== event.pointerId) return;
        if (event.type === 'pointermove') {
            this.#extend(gesture, event);
            return;
        }
        this.#gesture = null;
        this.#release(gesture);
        const operation = event.type === 'pointerup' ? this.#buildOperation(gesture) : null;
        if (operation === null) {
            this.#host.onCancel();
            return;
        }
        this.#host.onCommit(operation);
    }

    #begin(event: PointerEvent): void {
        if (this.#gesture !== null || !event.isPrimary || event.button !== 0 || !this.#host.isEnabled()) return;
        event.preventDefault();
        const style = this.#host.resolveStyle();
        const capacity = this.#host.capacity(isChatSketchShapeType(style.tool) ? 2 : 1, isChatSketchShapeType(style.tool) ? 'shape' : 'stroke');
        if (capacity.type === 'capacity-rejected') {
            this.#host.onCapacityRejected();
            return;
        }
        this.#host.canvas.setPointerCapture(event.pointerId);
        const box = measureViewportBox(this.#host.canvas);
        const displayScale = box.width > 0 ? this.#host.canvas.width / box.width : 1;
        const gesture: ActiveGesture = { pointerId: event.pointerId, style: { ...style, width: style.width * displayScale }, points: [this.#mapPoint(event, box)] };
        this.#gesture = gesture;
        this.#preview(gesture);
    }

    #extend(gesture: ActiveGesture, event: PointerEvent): void {
        const samples = typeof event.getCoalescedEvents === 'function' ? event.getCoalescedEvents() : [];
        const box = measureViewportBox(this.#host.canvas);
        for (const sample of samples.length > 0 ? samples : [event]) {
            const point = this.#mapPoint(sample, box);
            if (isChatSketchShapeType(gesture.style.tool)) {
                gesture.points[1] = point;
                continue;
            }
            const previous = gesture.points[gesture.points.length - 1];
            if (previous !== undefined && previous.x === point.x && previous.y === point.y) continue;
            if (this.#host.capacity(gesture.points.length + 1, 'stroke').type === 'capacity-rejected') {
                this.#reject(gesture);
                return;
            }
            gesture.points.push(point);
        }
        this.#preview(gesture);
    }

    #preview(gesture: ActiveGesture): void {
        this.#host.onPreview(this.#buildOperation(gesture));
    }

    #buildOperation(gesture: ActiveGesture): ChatSketchDrawOperation | null {
        const { tool, color, width } = gesture.style;
        const start = gesture.points[0];
        if (start === undefined) return null;
        if (!isChatSketchShapeType(tool)) return { type: 'stroke', tool, color, width, points: [...gesture.points] };
        const end = gesture.points[1];
        if (end === undefined || Math.max(Math.abs(end.x - start.x), Math.abs(end.y - start.y)) < MIN_SHAPE_EXTENT) return null;
        return { type: 'shape', shape: tool, color, width, start, end };
    }

    #mapPoint(event: PointerEvent, box: GeometryBox): ChatSketchPoint {
        const point = measureViewportPoint(event);
        const { width, height } = this.#host.canvas;
        const canvasX = box.width > 0 ? ((point.x - box.left) / box.width) * width : 0;
        const canvasY = box.height > 0 ? ((point.y - box.top) / box.height) * height : 0;
        return { x: clampNumber(canvasX, 0, width), y: clampNumber(canvasY, 0, height) };
    }
}

export { SketchPointerInputController };
