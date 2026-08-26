/* SoAI - Audio abstract MilkDrop-style feedback tunnel renderer [frontend/assets/ts/core/media/audioAbstractRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hsla, rgbToHue, type CanvasRgb, type CanvasSize } from '@core/media/audioVisualizerCanvas.ts';

const TWO_PI = Math.PI * 2;
const RING_POINTS = 160;
const ZOOM = 1.02;
const BASE_ROTATION = 0.0035;
const HUE_CYCLE = 0.03;
const SPIN_SPEED = 0.00035;
const BACKGROUND_BLOBS = 3;
const SPARKLE_COUNT = 14;
const PULSE_WAVES = 3;

type WaveSampler = (progress: number) => number;
type Ring = Readonly<{ hueOffset: number; radiusScale: number; phase: number; spinDirection: number }>;

const RINGS: readonly Ring[] = Object.freeze([Object.freeze({ hueOffset: 0, radiusScale: 0.2, phase: 0, spinDirection: 1 }), Object.freeze({ hueOffset: 130, radiusScale: 0.3, phase: TWO_PI / 3, spinDirection: -1 }), Object.freeze({ hueOffset: 245, radiusScale: 0.4, phase: (TWO_PI / 3) * 2, spinDirection: 1 })]);

const resolveEnergy = (sampler: WaveSampler): number => {
    const taps = 32;
    let total = 0;
    for (let tap = 0; tap < taps; tap += 1) {
        total += Math.abs(sampler(tap / taps));
    }
    return total / taps;
};

const warpPreviousFrame = (context: CanvasRenderingContext2D, size: CanvasSize, rotation: number): void => {
    const cx = size.width / 2;
    const cy = size.height / 2;
    context.save();
    context.globalCompositeOperation = 'source-over';
    context.globalAlpha = 1;
    context.transform(1, 0, 0, 1, cx, cy);
    context.rotate(rotation);
    context.scale(ZOOM, ZOOM);
    context.drawImage(context.canvas, -cx, -cy, size.width, size.height);
    context.restore();
};

const drawPulseRings = (context: CanvasRenderingContext2D, size: CanvasSize, baseHue: number, time: number, energy: number): void => {
    const cx = size.width / 2;
    const cy = size.height / 2;
    const maxRadius = Math.min(size.width, size.height) * 0.5;
    const intensity = Math.min(0.28, energy * 0.9);
    for (let wave = 0; wave < PULSE_WAVES; wave += 1) {
        const offset = wave / PULSE_WAVES;
        const alpha = intensity * (1 - offset * 0.35);
        if (alpha < 0.02) {
            continue;
        }
        const radius = maxRadius * (0.1 + offset * 0.16 + energy);
        context.strokeStyle = hsla(baseHue + time * HUE_CYCLE + wave * 40, 90, 66, alpha);
        context.lineWidth = 1 + energy * 2.5;
        context.beginPath();
        context.arc(cx, cy, radius, 0, TWO_PI);
        context.stroke();
    }
};

const drawSparkles = (context: CanvasRenderingContext2D, size: CanvasSize, baseHue: number, time: number, energy: number): void => {
    for (let spark = 0; spark < SPARKLE_COUNT; spark += 1) {
        const speed = 0.00018 + (spark % 4) * 0.00006;
        const sparkX = size.width * (0.5 + 0.46 * Math.sin(time * speed + spark * 1.13));
        const sparkY = size.height * (0.5 + 0.46 * Math.cos(time * speed * 1.3 + spark * 2.07));
        const twinkle = 0.5 + 0.5 * Math.sin(time * 0.004 + spark * 2);
        const radius = (1.6 + 1.4 * twinkle) * (1 + energy);
        const alpha = (0.12 + energy * 0.5) * twinkle;
        const hue = baseHue + time * HUE_CYCLE + spark * 31;
        const gradient = context.createRadialGradient(sparkX, sparkY, 0, sparkX, sparkY, radius);
        gradient.addColorStop(0, hsla(hue, 95, 82, alpha));
        gradient.addColorStop(1, hsla(hue, 95, 82, 0));
        context.fillStyle = gradient;
        context.beginPath();
        context.arc(sparkX, sparkY, radius, 0, TWO_PI);
        context.fill();
    }
};

const drawAnimatedBackground = (context: CanvasRenderingContext2D, size: CanvasSize, baseHue: number, time: number, energy: number): void => {
    const maxDimension = Math.max(size.width, size.height);
    const driftHue = baseHue + time * HUE_CYCLE;
    const decay = context.createLinearGradient(0, 0, size.width, size.height);
    decay.addColorStop(0, hsla(driftHue + 25, 72, 8 + energy * 10, 0.16));
    decay.addColorStop(1, hsla(driftHue - 35, 78, 5 + energy * 8, 0.18));
    context.globalCompositeOperation = 'source-over';
    context.globalAlpha = 1;
    context.fillStyle = decay;
    context.fillRect(0, 0, size.width, size.height);
    context.globalCompositeOperation = 'lighter';
    for (let blob = 0; blob < BACKGROUND_BLOBS; blob += 1) {
        const blobX = size.width * (0.5 + 0.42 * Math.sin(time * 0.00021 + blob * 2.1));
        const blobY = size.height * (0.5 + 0.42 * Math.cos(time * 0.00017 + blob * 1.7));
        const radius = maxDimension * (0.36 + 0.08 * Math.sin(time * 0.0003 + blob)) * (1 + energy * 0.6);
        const hue = driftHue + blob * 95;
        const gradient = context.createRadialGradient(blobX, blobY, 0, blobX, blobY, radius);
        gradient.addColorStop(0, hsla(hue, 88, 56, 0.05 + energy * 0.06));
        gradient.addColorStop(1, hsla(hue, 88, 56, 0));
        context.fillStyle = gradient;
        context.fillRect(0, 0, size.width, size.height);
    }
    drawPulseRings(context, size, baseHue, time, energy);
    drawSparkles(context, size, baseHue, time, energy);
};

const drawRing = (context: CanvasRenderingContext2D, size: CanvasSize, baseHue: number, time: number, ring: Ring, sampler: WaveSampler): void => {
    const cx = size.width / 2;
    const cy = size.height / 2;
    const baseRadius = Math.min(size.width, size.height) * ring.radiusScale;
    const spin = time * SPIN_SPEED * ring.spinDirection + ring.phase;
    context.lineWidth = 2.4;
    context.strokeStyle = hsla(baseHue + ring.hueOffset + time * HUE_CYCLE, 95, 63, 0.85);
    context.beginPath();
    for (let index = 0; index <= RING_POINTS; index += 1) {
        const progress = index / RING_POINTS;
        const radius = baseRadius * (1 + sampler(progress) * 0.55);
        const angle = progress * TWO_PI + spin;
        const xCoordinate = cx + Math.cos(angle) * radius;
        const yCoordinate = cy + Math.sin(angle) * radius;
        if (index === 0) {
            context.moveTo(xCoordinate, yCoordinate);
        } else {
            context.lineTo(xCoordinate, yCoordinate);
        }
    }
    context.closePath();
    context.stroke();
};

const drawAbstract = (context: CanvasRenderingContext2D, size: CanvasSize, color: CanvasRgb, time: number, sampler: WaveSampler): void => {
    const baseHue = rgbToHue(color);
    const energy = resolveEnergy(sampler);
    warpPreviousFrame(context, size, BASE_ROTATION + energy * 0.02);
    drawAnimatedBackground(context, size, baseHue, time, energy);
    context.globalCompositeOperation = 'lighter';
    context.lineCap = 'round';
    context.lineJoin = 'round';
    for (const ring of RINGS) {
        drawRing(context, size, baseHue, time, ring, sampler);
    }
    context.globalCompositeOperation = 'source-over';
};

const drawAbstractActive = (context: CanvasRenderingContext2D, size: CanvasSize, color: CanvasRgb, buffer: Uint8Array<ArrayBuffer>, time: number): void => {
    drawAbstract(context, size, color, time, (progress) => {
        const index = Math.min(buffer.length - 1, Math.floor(progress * buffer.length));
        return ((buffer[index] ?? 128) - 128) / 128;
    });
};

export { drawAbstractActive };
