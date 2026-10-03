/* SoAI - Chat sketch canvas proportion resize controller [frontend/assets/ts/pages/chat/controllers/modals/sketch/SketchResizeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { inlineDelta } from '@core/layout/direction.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { measureLayoutBox, measureLayoutPoint, measureLayoutViewport, type GeometryPoint } from '@core/layout/elementGeometry.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { CHAT_SKETCH_CANVAS_MAX_EXTENT, CHAT_SKETCH_CANVAS_MIN_EXTENT } from '@features/chat/public.ts';
import type { ChatSketchResizeHost, ChatSketchResizeTarget } from '@pages/chat/controllers/modals/sketch/types.ts';

type ResizeFrame = Readonly<{
    width: number;
    height: number;
    maxWidth: number;
    maxHeight: number;
    pixelsPerLayoutPixel: number;
}>;

type ResizeGesture = Readonly<{
    pointerId: number;
    origin: GeometryPoint;
    frame: ResizeFrame;
}>;

type ResizeDelta = Readonly<{
    width: number;
    height: number;
}>;

const DISPLAY_MIN_EXTENT = 160;
const DISPLAY_MAX_VIEWPORT_HEIGHT_RATIO = 0.7;
const KEYBOARD_STEP = 16;
const FRAME_WIDTH_PROPERTY = '--chat-sketch-frame-width';

const KEYBOARD_DELTAS: ReadonlyMap<string, ResizeDelta> = new Map([
    ['ArrowLeft', { width: -KEYBOARD_STEP, height: 0 }],
    ['ArrowRight', { width: KEYBOARD_STEP, height: 0 }],
    ['ArrowUp', { width: 0, height: -KEYBOARD_STEP }],
    ['ArrowDown', { width: 0, height: KEYBOARD_STEP }]
]);

class SketchResizeController {
    readonly #host: ChatSketchResizeHost;
    #gesture: ResizeGesture | null = null;
    #pending: ChatSketchResizeTarget | null = null;
    #frameId: number | null = null;

    constructor(host: ChatSketchResizeHost) {
        this.#host = host;
        const listener = (event: Event): void => {
            if (event instanceof PointerEvent) this.#handlePointer(event);
        };
        bindEventGroup(
            [
                { target: host.grip, type: 'pointerdown', listener },
                { target: host.grip, type: 'pointermove', listener },
                { target: host.grip, type: 'pointerup', listener },
                { target: host.grip, type: 'pointercancel', listener },
                { target: host.grip, type: 'lostpointercapture', listener },
                { target: host.grip, type: 'keydown', listener: (event: Event) => this.#handleKeydown(event) }
            ],
            host.signal
        );
    }

    isResizing(): boolean {
        return this.#gesture !== null;
    }

    dispose(): void {
        this.#gesture = null;
        this.#pending = null;
        this.#cancelFrame();
    }

    #handlePointer(event: PointerEvent): void {
        if (event.type === 'pointerdown') {
            this.#begin(event);
            return;
        }
        const gesture = this.#gesture;
        if (gesture === null || gesture.pointerId !== event.pointerId) return;
        if (event.type === 'pointercancel' || event.type === 'lostpointercapture') {
            this.dispose();
            return;
        }
        const point = measureLayoutPoint(event, this.#host.stage);
        this.#schedule(this.#resolveTarget(gesture.frame, { width: inlineDelta(point.x - gesture.origin.x, this.#host.grip), height: point.y - gesture.origin.y }));
        if (event.type === 'pointermove') return;
        this.#gesture = null;
        this.#flush();
    }

    #begin(event: PointerEvent): void {
        if (this.#gesture !== null || !event.isPrimary || event.button !== 0 || !this.#host.isEnabled()) return;
        event.preventDefault();
        this.#host.grip.setPointerCapture(event.pointerId);
        this.#gesture = { pointerId: event.pointerId, origin: measureLayoutPoint(event, this.#host.stage), frame: this.#measureFrame() };
    }

    #handleKeydown(event: Event): void {
        if (!(event instanceof KeyboardEvent) || event.altKey || event.ctrlKey || event.metaKey) return;
        const delta = KEYBOARD_DELTAS.get(event.key);
        if (delta === undefined || this.#gesture !== null || !this.#host.isEnabled()) return;
        event.preventDefault();
        this.#schedule(this.#resolveTarget(this.#measureFrame(), { width: inlineDelta(delta.width, this.#host.grip), height: delta.height }));
        this.#flush();
    }

    #measureFrame(): ResizeFrame {
        const canvasBox = measureLayoutBox(this.#host.canvas);
        const stageBox = measureLayoutBox(this.#host.stage);
        const viewport = measureLayoutViewport(this.#host.stage);
        return {
            width: canvasBox.width,
            height: canvasBox.height,
            maxWidth: Math.max(DISPLAY_MIN_EXTENT, canvasBox.width, stageBox.width),
            maxHeight: Math.max(DISPLAY_MIN_EXTENT, canvasBox.height, viewport.height * DISPLAY_MAX_VIEWPORT_HEIGHT_RATIO),
            pixelsPerLayoutPixel: canvasBox.width > 0 ? this.#host.canvas.width / canvasBox.width : 1
        };
    }

    #resolveTarget(frame: ResizeFrame, delta: ResizeDelta): ChatSketchResizeTarget {
        const displayWidth = clampNumber(frame.width + delta.width, DISPLAY_MIN_EXTENT, frame.maxWidth);
        const displayHeight = clampNumber(frame.height + delta.height, DISPLAY_MIN_EXTENT, frame.maxHeight);
        const sheetScale = Math.min(frame.pixelsPerLayoutPixel, CHAT_SKETCH_CANVAS_MAX_EXTENT / Math.max(displayWidth, displayHeight));
        return {
            displayWidth,
            sheetWidth: Math.max(CHAT_SKETCH_CANVAS_MIN_EXTENT, Math.round(displayWidth * sheetScale)),
            sheetHeight: Math.max(CHAT_SKETCH_CANVAS_MIN_EXTENT, Math.round(displayHeight * sheetScale))
        };
    }

    #schedule(target: ChatSketchResizeTarget): void {
        this.#pending = target;
        if (this.#frameId !== null) return;
        this.#frameId = getRequestAnimationFrame()(() => {
            this.#frameId = null;
            this.#apply();
        });
    }

    #flush(): void {
        this.#cancelFrame();
        this.#apply();
    }

    #cancelFrame(): void {
        if (this.#frameId === null) return;
        getCancelAnimationFrame()(this.#frameId);
        this.#frameId = null;
    }

    #apply(): void {
        const target = this.#pending;
        this.#pending = null;
        if (target === null) return;
        this.#host.stage.style.setProperty(FRAME_WIDTH_PROPERTY, `${String(target.displayWidth)}px`);
        this.#host.onResize(target);
    }
}

export { SketchResizeController };
