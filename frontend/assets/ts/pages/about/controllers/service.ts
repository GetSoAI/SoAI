/* SoAI - About page controllers service [frontend/assets/ts/pages/about/controllers/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { initializeAmbientParticles, triggerColorRipple } from '@pages/about/controllers/effects.ts';
import { setAnimationPhase, tickAnimationFrame } from '@pages/about/controllers/events.ts';
import { ParticleCanvasRenderer } from '@pages/about/controllers/particleCanvasRendererController.ts';
import { createInitialAnimationState } from '@pages/about/controllers/state.ts';
import type { AnimationHost, AnimationPhase, AnimationState } from '@pages/about/controllers/types.ts';

class EasterEggAnimation {
    readonly #resources = new ResourceTracker();
    readonly #renderer = new ParticleCanvasRenderer();
    #host: AnimationHost | null = null;
    #state: AnimationState = createInitialAnimationState();

    initialize(host: AnimationHost): void {
        this.#host = host;
        const scene = host.getScene();
        if (!scene) {
            return;
        }
        const track = this.#resources;
        track.addEventListener(scene, 'mousemove', this.#handleMouseMove);
        track.addEventListener(scene, 'mouseleave', this.#handleMouseLeave);
        track.addEventListener(scene, 'click', this.#handleClick);
        track.addEventListener(scene, 'keydown', this.#handleKeyDown);
        const canvas = host.getParticleCanvas();
        if (canvas) {
            this.#renderer.initialize(canvas);
        }
        initializeAmbientParticles(this.#state, this.#host);
        setAnimationPhase(this.#state, this.#host, 'idle');
        this.#startAnimationLoop();
    }

    cleanup(): void {
        this.#resources.cleanup();
        this.#state.animationFrame = null;
        this.#state.particles = [];
        this.#renderer.cleanup();
        this.#state.starfieldElement?.remove();
        this.#state.starfieldElement = null;
        this.#host = null;
    }

    #startAnimationLoop = (): void => {
        const tick = (timestamp: number): void => {
            const host = this.#host;
            if (host) {
                tickAnimationFrame(timestamp, this.#state, host, this.#renderer);
                this.#state.animationFrame = this.#resources.requestAnimationFrame(tick);
                return;
            }
            this.#state.animationFrame = null;
        };
        this.#state.animationFrame = this.#resources.requestAnimationFrame(tick);
    };

    #setPhase(phase: AnimationPhase): void {
        setAnimationPhase(this.#state, this.#host, phase);
    }

    #handleMouseMove = (event: Event): void => {
        const scene = this.#host?.getScene();
        if (!(event instanceof MouseEvent) || !scene) {
            return;
        }
        const rect = measureLayoutBox(scene);
        const point = measureLayoutPoint(event, scene);
        this.#state.cursorPosition = {
            x: point.x - rect.left,
            y: point.y - rect.top
        };
        this.#state.lastMouseMoveTime = performance.now();
        if (this.#state.phase === 'idle') {
            this.#setPhase('hover');
        }
    };

    #handleMouseLeave = (): void => {
        this.#state.cursorPosition = null;
        if (this.#state.phase === 'hover') {
            this.#setPhase('idle');
        }
        const orb = this.#host?.getOrb();
        if (orb) {
            orb.style.setProperty('transform', '');
        }
        const glowElement = this.#host?.getGlowElement();
        if (glowElement) {
            glowElement.style.setProperty('opacity', '0.6');
        }
    };

    #handleClick = (): void => {
        if (this.#state.phase !== 'idle' && this.#state.phase !== 'hover') {
            return;
        }
        this.#triggerColorRipple();
    };

    #handleKeyDown = (event: Event): void => {
        if (!(event instanceof KeyboardEvent)) {
            return;
        }
        if (event.key !== 'Enter' && event.key !== ' ') {
            return;
        }
        if (this.#state.phase !== 'idle' && this.#state.phase !== 'hover') {
            return;
        }
        event.preventDefault();
        this.#triggerColorRipple();
    };

    #triggerColorRipple(): void {
        triggerColorRipple(this.#state, this.#host);
    }
}

export { EasterEggAnimation };
