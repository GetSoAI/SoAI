/* SoAI - Shared modals layout policy [frontend/assets/ts/core/modals/modalhost/layoutPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalConfig, Position, SavedModalState } from '@core/modals/types.ts';
import { calculateModalBoundaries } from '@core/modals/modalhost/effects.ts';
import type { ModalBoundsDependencies } from '@core/modals/modalhost/types.ts';

const shouldPersistModalDesktopState = (isMobileViewport: boolean): boolean => {
    return isMobileViewport === false;
};

const sanitizeSavedModalState = (savedState: SavedModalState | null): SavedModalState | null => {
    if (!savedState?.size) {
        return null;
    }
    const width = savedState.size.width;
    const height = savedState.size.height;
    if (!Number.isFinite(width) || !Number.isFinite(height)) {
        return null;
    }
    return { size: { width, height } };
};

const resolveCenteredPosition = ({ content, isMobileViewport, sizeOverride = null }: ModalBoundsDependencies): Position => {
    const boundaries = calculateModalBoundaries({ content, isMobileViewport, sizeOverride });
    return {
        x: (boundaries.minX + boundaries.maxX) / 2,
        y: (boundaries.minY + boundaries.maxY) / 2
    };
};

const shouldShowFullscreenControl = (config: ModalConfig, isMobileViewport: boolean): boolean => {
    return config.allowFullscreen && isMobileViewport === false;
};

export { resolveCenteredPosition, sanitizeSavedModalState, shouldPersistModalDesktopState, shouldShowFullscreenControl };
