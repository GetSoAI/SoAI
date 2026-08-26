/* SoAI - About page particle canvas renderer controller [frontend/assets/ts/pages/about/controllers/particleCanvasRendererController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Particle } from '@pages/about/controllers/easterEggParticles.ts';
import { resolveCanvasRenderPixelRatio } from '@core/layout/canvasGeometry.ts';

const SPRITE_SIZE = 64;
const SPRITE_CORE_STOP = 0.35;
const SPRITE_GLOW_SCALE = 3;
const TRAIL_SPEED_THRESHOLD = 1.5;
const TRAIL_OFFSET_FACTOR = 2;
const TRAIL_ALPHA_FACTOR = 0.35;

interface RgbComponents {
    red: number;
    green: number;
    blue: number;
}

export class ParticleCanvasRenderer {
    #canvas: HTMLCanvasElement | null = null;
    #context: CanvasRenderingContext2D | null = null;
    readonly #sprites = new Map<string, HTMLCanvasElement>();

    initialize(canvas: HTMLCanvasElement): void {
        const context = canvas.getContext('2d');
        if (!context) {
            throw new Error('Easter egg particle canvas 2d context unavailable');
        }
        this.#canvas = canvas;
        this.#context = context;
        this.#sprites.clear();
        this.#syncCanvasSize();
    }

    cleanup(): void {
        const canvas = this.#canvas;
        const context = this.#context;
        if (canvas && context) {
            context.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
        }
        this.#sprites.clear();
        this.#canvas = null;
        this.#context = null;
    }

    render(particles: readonly Particle[]): void {
        const canvas = this.#canvas;
        const context = this.#context;
        if (!canvas || !context) {
            return;
        }
        this.#syncCanvasSize();
        context.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
        for (const particle of particles) {
            const sprite = this.#resolveSprite(particle.color);
            const drawSize = particle.size * particle.scale * SPRITE_GLOW_SCALE;
            const half = drawSize / 2;
            const speed = Math.abs(particle.vx) + Math.abs(particle.vy);
            if (speed > TRAIL_SPEED_THRESHOLD) {
                context.globalAlpha = particle.opacity * TRAIL_ALPHA_FACTOR;
                context.drawImage(sprite, particle.x - particle.vx * TRAIL_OFFSET_FACTOR - half, particle.y - particle.vy * TRAIL_OFFSET_FACTOR - half, drawSize, drawSize);
            }
            context.globalAlpha = particle.opacity;
            context.drawImage(sprite, particle.x - half, particle.y - half, drawSize, drawSize);
        }
        context.globalAlpha = 1;
    }

    #syncCanvasSize(): void {
        const canvas = this.#canvas;
        const context = this.#context;
        if (!canvas || !context) {
            return;
        }
        const pixelRatio = resolveCanvasRenderPixelRatio(canvas);
        const width = Math.max(1, Math.round(canvas.clientWidth * pixelRatio));
        const height = Math.max(1, Math.round(canvas.clientHeight * pixelRatio));
        if (canvas.width !== width || canvas.height !== height) {
            canvas.width = width;
            canvas.height = height;
            context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        }
    }

    #resolveSprite(color: string): HTMLCanvasElement {
        const cached = this.#sprites.get(color);
        if (cached) {
            return cached;
        }
        const sprite = this.#createSprite(color);
        this.#sprites.set(color, sprite);
        return sprite;
    }

    #createSprite(color: string): HTMLCanvasElement {
        const sprite = document.createElement('canvas');
        sprite.width = SPRITE_SIZE;
        sprite.height = SPRITE_SIZE;
        const context = sprite.getContext('2d');
        if (!context) {
            throw new Error('Easter egg particle sprite 2d context unavailable');
        }
        const components = this.#resolveColorComponents(this.#resolveCssColor(color));
        const half = SPRITE_SIZE / 2;
        const gradient = context.createRadialGradient(half, half, 0, half, half, half);
        gradient.addColorStop(0, `rgba(${components.red}, ${components.green}, ${components.blue}, 1)`);
        gradient.addColorStop(SPRITE_CORE_STOP, `rgba(${components.red}, ${components.green}, ${components.blue}, 0.9)`);
        gradient.addColorStop(1, `rgba(${components.red}, ${components.green}, ${components.blue}, 0)`);
        context.fillStyle = gradient;
        context.fillRect(0, 0, SPRITE_SIZE, SPRITE_SIZE);
        return sprite;
    }

    #resolveCssColor(color: string): string {
        if (!color.startsWith('var(')) {
            return color;
        }
        const canvas = this.#canvas;
        if (!canvas) {
            throw new Error('Easter egg particle canvas missing for CSS color resolution');
        }
        const variableName = color.slice(4, -1).trim();
        const resolved = window.getComputedStyle(canvas).getPropertyValue(variableName).trim();
        if (!resolved) {
            throw new Error(`Easter egg particle color variable "${variableName}" is not defined`);
        }
        return resolved;
    }

    #resolveColorComponents(color: string): RgbComponents {
        const probe = document.createElement('canvas');
        probe.width = 1;
        probe.height = 1;
        const context = probe.getContext('2d');
        if (!context) {
            throw new Error('Easter egg particle color probe 2d context unavailable');
        }
        context.fillStyle = color;
        context.fillRect(0, 0, 1, 1);
        const data = context.getImageData(0, 0, 1, 1).data;
        return { red: data[0] ?? 0, green: data[1] ?? 0, blue: data[2] ?? 0 };
    }
}
