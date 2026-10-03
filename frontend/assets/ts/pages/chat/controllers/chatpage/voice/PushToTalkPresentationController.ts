/* SoAI - Push-to-talk initiating microphone presentation [frontend/assets/ts/pages/chat/controllers/chatpage/voice/PushToTalkPresentationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { inlineDelta, isRtl } from '@core/layout/direction.ts';
import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { isReducedAnimationScope, scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { measureLayoutBox, measureLayoutViewport, type GeometryPoint } from '@core/layout/elementGeometry.ts';
import type { AudioRecordingTimerHost } from '@features/chat/public.ts';

const PUSH_TO_TALK_CANCEL_DISTANCE_PX = 88;
const PUSH_TO_TALK_CANCEL_MINIMUM_PX = 16;
const PUSH_TO_TALK_VIEWPORT_MARGIN_PX = 8;
const PUSH_TO_TALK_DRAG_DEAD_ZONE_PX = 10;
const PUSH_TO_TALK_DISARM_HYSTERESIS_PX = 12;
const PUSH_TO_TALK_RECORDING_SCALE = 1.08;

interface PushToTalkVisualState {
    translateX: number;
    progress: number;
    cancellationArmed: boolean;
}

class PushToTalkPresentationController {
    readonly #button: HTMLButtonElement;
    readonly #start: GeometryPoint;
    readonly #cancelDistance: number;
    readonly #maximumTranslation: number;
    readonly #renderQueue: AnimationFrameRenderQueue<PushToTalkVisualState>;
    readonly #timers: AudioRecordingTimerHost;
    #cancellationArmed = false;
    #returnTimer: number | null = null;
    #returning = false;
    #disposed = false;

    constructor(button: HTMLButtonElement, start: GeometryPoint, timers: AudioRecordingTimerHost) {
        this.#button = button;
        this.#start = start;
        this.#timers = timers;
        const box = measureLayoutBox(button);
        const viewportWidth = measureLayoutViewport(button).width;
        const inlineStartDistance = isRtl(button) ? viewportWidth - start.x : start.x;
        const inlineStartEdge = isRtl(button) ? viewportWidth - box.right : box.left;
        const availableDistance = Math.max(0, inlineStartDistance - PUSH_TO_TALK_VIEWPORT_MARGIN_PX);
        this.#cancelDistance = Math.min(PUSH_TO_TALK_CANCEL_DISTANCE_PX, Math.max(PUSH_TO_TALK_CANCEL_MINIMUM_PX, availableDistance));
        const scaledInlineExpansion = (box.width * (PUSH_TO_TALK_RECORDING_SCALE - 1)) / 2;
        this.#maximumTranslation = Math.max(0, inlineStartEdge - PUSH_TO_TALK_VIEWPORT_MARGIN_PX - scaledInlineExpansion);
        this.#renderQueue = new AnimationFrameRenderQueue({
            label: 'PushToTalkPresentation',
            merge: (_previous, next) => next,
            isDisposed: () => this.#disposed,
            render: (state) => this.#render(state)
        });
        button.classList.add('is-ptt-initiator');
        button.classList.toggle('is-ptt-reduced-motion', isReducedAnimationScope(button));
        button.style.setProperty('--ptt-recording-scale', String(PUSH_TO_TALK_RECORDING_SCALE));
        button.style.setProperty('--ptt-microphone-opacity', '1');
        button.style.setProperty('--ptt-activation-duration', `${scaleAnimationDurationMs(150, button)}ms`);
        button.style.setProperty('--ptt-return-duration', `${scaleAnimationDurationMs(160, button)}ms`);
    }

    get cancellationArmed(): boolean {
        return this.#cancellationArmed;
    }

    markRecordingStarted(): void {
        if (!this.#disposed) this.#button.classList.add('is-ptt-recording');
    }

    move(current: GeometryPoint): boolean {
        if (this.#disposed) return false;
        const displacement = Math.max(0, inlineDelta(this.#start.x - current.x, this.#button));
        if (!this.#cancellationArmed && displacement >= this.#cancelDistance) this.#cancellationArmed = true;
        else if (this.#cancellationArmed && displacement <= this.#cancelDistance - PUSH_TO_TALK_DISARM_HYSTERESIS_PX) this.#cancellationArmed = false;
        const dragDistance = Math.max(0, displacement - PUSH_TO_TALK_DRAG_DEAD_ZONE_PX);
        const progressRange = Math.max(1, this.#cancelDistance - PUSH_TO_TALK_DRAG_DEAD_ZONE_PX);
        this.#renderQueue.schedule({
            translateX: inlineDelta(-Math.min(dragDistance, this.#maximumTranslation), this.#button),
            progress: Math.min(1, dragDistance / progressRange),
            cancellationArmed: this.#cancellationArmed
        });
        return this.#cancellationArmed;
    }

    finish(): void {
        if (this.#disposed || this.#returning) return;
        this.#returning = true;
        this.#renderQueue.cancel();
        this.#button.classList.add('is-ptt-returning');
        this.#button.classList.remove('is-ptt-cancel-armed');
        this.#button.style.setProperty('--ptt-translate-x', '0px');
        this.#button.style.setProperty('--ptt-cancel-progress', '0');
        this.#button.style.setProperty('--ptt-microphone-opacity', '1');
        const duration = scaleAnimationDurationMs(160, this.#button);
        if (duration === 0) {
            this.dispose();
            return;
        }
        this.#returnTimer = this.#timers.setTimeout(() => this.dispose(), duration);
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        if (this.#returnTimer !== null) this.#timers.clearTimeout(this.#returnTimer);
        this.#returnTimer = null;
        this.#renderQueue.dispose();
        this.#button.classList.remove('is-ptt-initiator', 'is-ptt-recording', 'is-ptt-cancel-armed', 'is-ptt-returning', 'is-ptt-reduced-motion');
        this.#button.style.removeProperty('--ptt-translate-x');
        this.#button.style.removeProperty('--ptt-cancel-progress');
        this.#button.style.removeProperty('--ptt-recording-scale');
        this.#button.style.removeProperty('--ptt-microphone-opacity');
        this.#button.style.removeProperty('--ptt-activation-duration');
        this.#button.style.removeProperty('--ptt-return-duration');
    }

    #render(state: PushToTalkVisualState): void {
        this.#button.style.setProperty('--ptt-translate-x', `${state.translateX}px`);
        this.#button.style.setProperty('--ptt-cancel-progress', String(state.progress));
        this.#button.style.setProperty('--ptt-microphone-opacity', String(1 - state.progress));
        this.#button.classList.toggle('is-ptt-cancel-armed', state.cancellationArmed);
    }
}

export { PUSH_TO_TALK_CANCEL_DISTANCE_PX, PUSH_TO_TALK_DISARM_HYSTERESIS_PX, PushToTalkPresentationController };
