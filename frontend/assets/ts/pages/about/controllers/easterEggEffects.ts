/* SoAI - About page easter egg effects [frontend/assets/ts/pages/about/controllers/easterEggEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { randomInRange } from '@pages/about/controllers/easterEggParticles.ts';

export const createStarfield = (container: HTMLElement, count: number): HTMLElement => {
    const existing = dom.resolve('.easter-egg-starfield', container);
    let element: HTMLElement;
    if (existing instanceof HTMLElement) {
        element = existing;
    } else {
        element = document.createElement('div');
        element.className = 'easter-egg-starfield';
        container.insertBefore(element, container.firstChild);
    }
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 300;
    const shadows: string[] = [];
    for (let starIndex = 0; starIndex < count; starIndex++) {
        const positionX = randomInRange(0, width);
        const positionY = randomInRange(0, height);
        const starSize = randomInRange(0.5, 1.5);
        const starOpacity = randomInRange(0.2, 0.7);
        shadows.push(`${positionX}px ${positionY}px ${starSize}px rgba(255, 255, 255, ${starOpacity})`);
    }
    element.style.setProperty('width', '1px');
    element.style.setProperty('height', '1px');
    element.style.setProperty('box-shadow', shadows.join(', '));
    return element;
};

export const calculateGlowIntensity = (cursorX: number, cursorY: number, centerX: number, centerY: number, maxDistance: number): number => {
    const deltaX = cursorX - centerX;
    const deltaY = cursorY - centerY;
    const distance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
    return Math.max(0, 1 - distance / maxDistance);
};
