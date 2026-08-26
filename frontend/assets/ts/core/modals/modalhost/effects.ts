/* SoAI - Shared modals modalhost effects [frontend/assets/ts/core/modals/modalhost/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { calculateModalTranslateBoundaries } from '@core/modals/modalhost/geometry.ts';
import type { Boundaries, ModalBoundsDependencies, ModalPositionDependencies } from '@core/modals/modalhost/types.ts';
import type { Position } from '@core/modals/types.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber, isObject } from '@core/typeGuards.ts';

const MODAL_TRANSLATE_X_PROPERTY = '--motion-modal-translate-x';
const MODAL_TRANSLATE_Y_PROPERTY = '--motion-modal-translate-y';

const formatPositionValue = (value: number): string => `${value}px`;

const readPositionValue = (content: Element, property: string): number => {
    if (!(content instanceof HTMLElement)) {
        return 0;
    }
    const raw = content.style.getPropertyValue(property).trim() || getComputedStyle(content).getPropertyValue(property).trim();
    if (!raw) {
        return 0;
    }
    const parsed = Number.parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : 0;
};

const validatePosition = (position: Position | null | undefined): Position | null => {
    if (!isObject(position)) {
        return null;
    }
    const xCoordinate = position['x'];
    const yCoordinate = position['y'];
    if (!isFiniteNumber(xCoordinate) || !isFiniteNumber(yCoordinate)) {
        return null;
    }
    return { x: xCoordinate, y: yCoordinate };
};

const applyPosition = (content: Element | null, position: Position | null): void => {
    if (content instanceof HTMLElement && position) {
        content.style.setProperty(MODAL_TRANSLATE_X_PROPERTY, formatPositionValue(position.x));
        content.style.setProperty(MODAL_TRANSLATE_Y_PROPERTY, formatPositionValue(position.y));
    }
};

const getTransformTranslate = (content: Element): Position | null => {
    if (content instanceof HTMLElement) {
        return {
            x: readPositionValue(content, MODAL_TRANSLATE_X_PROPERTY),
            y: readPositionValue(content, MODAL_TRANSLATE_Y_PROPERTY)
        };
    }
    const transform = dom.getStyleValue(content, 'transform') || '';
    if (transform === 'none') {
        return { x: 0, y: 0 };
    }

    const translateMatch = transform.match(/translate\\(\\s*(-?\\d+(?:\\.\\d+)?)px,\\s*(-?\\d+(?:\\.\\d+)?)px\\s*\\)/);
    if (translateMatch && isFiniteNumber(Number.parseFloat(translateMatch[1] || '0')) && isFiniteNumber(Number.parseFloat(translateMatch[2] || '0'))) {
        return {
            x: Number.parseFloat(translateMatch[1] || '0'),
            y: Number.parseFloat(translateMatch[2] || '0')
        };
    }

    const translate3dMatch = transform.match(/translate3d\\(\\s*(-?\\d+(?:\\.\\d+)?)px,\\s*(-?\\d+(?:\\.\\d+)?)px,\\s*(-?\\d+(?:\\.\\d+)?)px\\s*\\)/);
    if (translate3dMatch && isFiniteNumber(Number.parseFloat(translate3dMatch[1] || '0')) && isFiniteNumber(Number.parseFloat(translate3dMatch[2] || '0'))) {
        return {
            x: Number.parseFloat(translate3dMatch[1] || '0'),
            y: Number.parseFloat(translate3dMatch[2] || '0')
        };
    }

    const matrixMatch = transform.match(/matrix\\(([^)]+)\\)/);
    if (matrixMatch) {
        const values = (matrixMatch[1] || '').split(',').map((value) => Number.parseFloat(value.trim()));
        const xCoordinate = values[4];
        const yCoordinate = values[5];
        if (isFiniteNumber(xCoordinate) && isFiniteNumber(yCoordinate)) {
            return { x: xCoordinate, y: yCoordinate };
        }
    }

    const matrix3dMatch = transform.match(/matrix3d\\(([^)]+)\\)/);
    if (matrix3dMatch) {
        const values = (matrix3dMatch[1] || '').split(',').map((value) => Number.parseFloat(value.trim()));
        const xCoordinate = values[12];
        const yCoordinate = values[13];
        if (isFiniteNumber(xCoordinate) && isFiniteNumber(yCoordinate)) {
            return { x: xCoordinate, y: yCoordinate };
        }
    }

    return { x: 0, y: 0 };
};

const calculateModalBoundaries = ({ content, isMobileViewport, sizeOverride = null }: ModalBoundsDependencies): Boundaries => {
    const measuredSize = sizeOverride ?? measureLayoutBox(content);
    const width = Math.max(measuredSize.width, 1);
    const height = Math.max(measuredSize.height, 1);
    return calculateModalTranslateBoundaries({ content, width, height, isMobileViewport });
};

const clampPosition = ({ content, position, isMobileViewport, sizeOverride = null }: ModalPositionDependencies): Position => {
    const boundaries = calculateModalBoundaries({ content, isMobileViewport, sizeOverride });
    return {
        x: clampNumber(position.x, boundaries.minX, boundaries.maxX),
        y: clampNumber(position.y, boundaries.minY, boundaries.maxY)
    };
};

const enforceBoundaries = ({ content, isMobileViewport, sizeOverride = null }: ModalBoundsDependencies): Position | null => {
    const current = getTransformTranslate(content);
    if (!current) {
        return null;
    }
    const clamped = clampPosition({ content, position: current, isMobileViewport, sizeOverride });
    if (clamped.x !== current.x || clamped.y !== current.y) {
        applyPosition(content, clamped);
    }
    return clamped;
};

export { applyPosition, calculateModalBoundaries, clampPosition, enforceBoundaries, getTransformTranslate, isFiniteNumber, validatePosition };
