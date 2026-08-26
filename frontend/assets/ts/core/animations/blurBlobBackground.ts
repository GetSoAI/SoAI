/* SoAI - Shared animations blur blob background [frontend/assets/ts/core/animations/blurBlobBackground.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';

interface BlurBlobConfiguration {
    size: number;
    blurRadius: number;
    opacity: number;
    cssColor: string;
    maxSpeed: number;
    wanderStrength: number;
    damping: number;
    pulseSpeed: number;
    pulseAmplitude: number;
}

interface BlurBlobState {
    element: HTMLDivElement;
    positionX: number;
    positionY: number;
    velocityX: number;
    velocityY: number;
    maxSpeed: number;
    wanderStrength: number;
    damping: number;
    pulseSpeed: number;
    pulseAmplitude: number;
    phaseOffset: number;
    blobSize: number;
}

interface BlurBlobBackgroundOptions {
    onError?: (operation: string, error: Error) => void;
    blobClassName?: string;
    configurations?: ReadonlyArray<BlurBlobConfiguration>;
}

const DEFAULT_BLOB_CLASS_NAME = 'blur-blob';
const EDGE_REPULSION_MARGIN = 0.15;
const EDGE_REPULSION_STRENGTH = 0.03;
const FULL_CIRCLE = Math.PI * 2;

const DEFAULT_BLUR_BLOB_CONFIGURATIONS: ReadonlyArray<BlurBlobConfiguration> = [
    { size: 300, blurRadius: 100, opacity: 0.06, cssColor: 'var(--accent-green)', maxSpeed: 0.35, wanderStrength: 0.012, damping: 0.997, pulseSpeed: 0.0005, pulseAmplitude: 0.12 },
    { size: 240, blurRadius: 80, opacity: 0.045, cssColor: '#c8b832', maxSpeed: 0.4, wanderStrength: 0.015, damping: 0.996, pulseSpeed: 0.0008, pulseAmplitude: 0.1 },
    { size: 340, blurRadius: 120, opacity: 0.035, cssColor: '#a0b040', maxSpeed: 0.25, wanderStrength: 0.009, damping: 0.998, pulseSpeed: 0.0004, pulseAmplitude: 0.15 },
    { size: 200, blurRadius: 70, opacity: 0.055, cssColor: '#d4c244', maxSpeed: 0.45, wanderStrength: 0.018, damping: 0.995, pulseSpeed: 0.0009, pulseAmplitude: 0.08 },
    { size: 270, blurRadius: 90, opacity: 0.04, cssColor: 'var(--accent-green)', maxSpeed: 0.3, wanderStrength: 0.013, damping: 0.997, pulseSpeed: 0.0006, pulseAmplitude: 0.11 }
];

const randomInRange = (minimum: number, maximum: number): number => {
    return minimum + Math.random() * (maximum - minimum);
};

const clampSpeed = (velocityX: number, velocityY: number, limit: number): { clampedX: number; clampedY: number } => {
    const speedSquared = velocityX * velocityX + velocityY * velocityY;
    if (speedSquared <= limit * limit) {
        return { clampedX: velocityX, clampedY: velocityY };
    }
    const speed = Math.sqrt(speedSquared);
    const scale = limit / speed;
    return { clampedX: velocityX * scale, clampedY: velocityY * scale };
};

const createBlobElement = (config: BlurBlobConfiguration, blobClassName: string): HTMLDivElement => {
    const element = document.createElement('div');
    element.className = blobClassName;
    element.style.width = `${config.size}px`;
    element.style.height = `${config.size}px`;
    element.style.backgroundColor = config.cssColor;
    element.style.opacity = String(config.opacity);
    element.style.filter = `blur(${config.blurRadius}px)`;
    return element;
};

const createBlobState = (element: HTMLDivElement, config: BlurBlobConfiguration, containerWidth: number, containerHeight: number): BlurBlobState => {
    const halfSize = config.size / 2;
    return {
        element,
        positionX: randomInRange(-halfSize, containerWidth - halfSize),
        positionY: randomInRange(-halfSize, containerHeight - halfSize),
        velocityX: randomInRange(-config.maxSpeed, config.maxSpeed) * 0.5,
        velocityY: randomInRange(-config.maxSpeed, config.maxSpeed) * 0.5,
        maxSpeed: config.maxSpeed,
        wanderStrength: config.wanderStrength,
        damping: config.damping,
        pulseSpeed: config.pulseSpeed,
        pulseAmplitude: config.pulseAmplitude,
        phaseOffset: Math.random() * FULL_CIRCLE,
        blobSize: config.size
    };
};

const applyEdgeRepulsion = (blob: BlurBlobState, containerWidth: number, containerHeight: number): void => {
    const halfSize = blob.blobSize / 2;
    const marginX = containerWidth * EDGE_REPULSION_MARGIN;
    const marginY = containerHeight * EDGE_REPULSION_MARGIN;
    const centerX = blob.positionX + halfSize;
    const centerY = blob.positionY + halfSize;

    if (centerX < marginX) {
        blob.velocityX += ((marginX - centerX) / marginX) * EDGE_REPULSION_STRENGTH;
    } else if (centerX > containerWidth - marginX) {
        blob.velocityX -= ((centerX - (containerWidth - marginX)) / marginX) * EDGE_REPULSION_STRENGTH;
    }

    if (centerY < marginY) {
        blob.velocityY += ((marginY - centerY) / marginY) * EDGE_REPULSION_STRENGTH;
    } else if (centerY > containerHeight - marginY) {
        blob.velocityY -= ((centerY - (containerHeight - marginY)) / marginY) * EDGE_REPULSION_STRENGTH;
    }
};

const updateBlob = (blob: BlurBlobState, containerWidth: number, containerHeight: number, elapsedMs: number): void => {
    const wanderAngle = Math.random() * FULL_CIRCLE;
    blob.velocityX += Math.cos(wanderAngle) * blob.wanderStrength;
    blob.velocityY += Math.sin(wanderAngle) * blob.wanderStrength;

    applyEdgeRepulsion(blob, containerWidth, containerHeight);

    blob.velocityX *= blob.damping;
    blob.velocityY *= blob.damping;

    const clamped = clampSpeed(blob.velocityX, blob.velocityY, blob.maxSpeed);
    blob.velocityX = clamped.clampedX;
    blob.velocityY = clamped.clampedY;

    blob.positionX += blob.velocityX;
    blob.positionY += blob.velocityY;

    const pulsePhase = elapsedMs * blob.pulseSpeed + blob.phaseOffset;
    const scale = 1 + Math.sin(pulsePhase) * blob.pulseAmplitude;

    blob.element.style.transform = `translate(${blob.positionX}px, ${blob.positionY}px) scale(${scale.toFixed(3)})`;
};

const noopErrorHandler = (_operation: string, _error: Error): void => {};

type BlurBlobBackgroundCleanup = () => void;

const startBlurBlobBackground = (container: HTMLElement, options: BlurBlobBackgroundOptions = {}): BlurBlobBackgroundCleanup => {
    const resources = new ResourceTracker();
    const onError = options.onError ?? noopErrorHandler;
    const blobClassName = options.blobClassName ?? DEFAULT_BLOB_CLASS_NAME;
    const configurations = options.configurations ?? DEFAULT_BLUR_BLOB_CONFIGURATIONS;

    if (configurations.length === 0) {
        onError('blur-blob-background-init', new Error('No blob configurations were provided'));
        return () => {};
    }

    let destroyed = false;
    let frameId = 0;
    let startTime = 0;
    let containerWidth = container.clientWidth;
    let containerHeight = container.clientHeight;

    if (containerWidth === 0 || containerHeight === 0) {
        onError('blur-blob-background-init', new Error('Container has zero dimensions'));
        return () => {};
    }

    const blobs: BlurBlobState[] = [];

    for (const configuration of configurations) {
        const element = createBlobElement(configuration, blobClassName);
        container.appendChild(element);
        blobs.push(createBlobState(element, configuration, containerWidth, containerHeight));
    }

    for (const blob of blobs) {
        blob.element.style.transform = `translate(${blob.positionX}px, ${blob.positionY}px) scale(1)`;
    }

    const renderFrame = (timestamp: number): void => {
        if (destroyed) {
            return;
        }
        if (startTime === 0) {
            startTime = timestamp;
        }
        const elapsedMs = timestamp - startTime;

        for (const blob of blobs) {
            updateBlob(blob, containerWidth, containerHeight, elapsedMs);
        }

        frameId = resources.requestAnimationFrame(renderFrame);
    };

    frameId = resources.requestAnimationFrame(renderFrame);

    const resizeObserver = new ResizeObserver(() => {
        if (destroyed) {
            return;
        }
        containerWidth = container.clientWidth;
        containerHeight = container.clientHeight;
    });
    resizeObserver.observe(container);

    return (): void => {
        if (destroyed) {
            return;
        }
        destroyed = true;
        resources.cancelAnimationFrame(frameId);
        resources.cleanup();
        resizeObserver.disconnect();
        for (const blob of blobs) {
            blob.element.remove();
        }
        blobs.length = 0;
    };
};

export { startBlurBlobBackground, DEFAULT_BLUR_BLOB_CONFIGURATIONS };
export type { BlurBlobBackgroundCleanup, BlurBlobBackgroundOptions, BlurBlobConfiguration };
