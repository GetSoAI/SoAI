/* SoAI - Shared status surface visibility updates [frontend/assets/ts/core/ui/statusSurface.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';

type StatusSurfaceTone = 'error' | 'info' | 'success' | 'warning';
type StatusSurfaceVisibility = 'hiddenAttribute' | 'hiddenClass';

interface StatusSurfaceOptions {
    surface: HTMLElement;
    message: string | null;
    tone?: StatusSurfaceTone | undefined;
    visibility?: StatusSurfaceVisibility | undefined;
    hiddenClassName?: string | undefined;
}

const normalizeStatusSurfaceMessage = (message: string | null): string => {
    if (message === null) {
        return '';
    }
    return message;
};

const applyStatusSurfaceVisibility = (surface: HTMLElement, visible: boolean, visibility: StatusSurfaceVisibility, hiddenClassName: string): void => {
    if (visibility === 'hiddenAttribute') {
        surface.hidden = !visible;
        if (visible) {
            surface.classList.remove(hiddenClassName);
        }
        return;
    }
    if (visible) {
        surface.hidden = false;
    }
    surface.classList.toggle(hiddenClassName, !visible);
};

const setStatusSurface = (options: StatusSurfaceOptions): void => {
    const message = normalizeStatusSurfaceMessage(options.message);
    const visibility = options.visibility ?? 'hiddenClass';
    const hiddenClassName = options.hiddenClassName ?? CSS_CLASSES.HIDDEN;
    options.surface.textContent = message;
    applyStatusSurfaceVisibility(options.surface, message.length > 0, visibility, hiddenClassName);
    if (options.tone !== undefined) {
        options.surface.dataset['tone'] = options.tone;
        return;
    }
    delete options.surface.dataset['tone'];
};

const clearStatusSurface = (surface: HTMLElement, visibility: StatusSurfaceVisibility = 'hiddenClass', hiddenClassName: string = CSS_CLASSES.HIDDEN): void => {
    setStatusSurface({
        surface,
        message: null,
        visibility,
        hiddenClassName
    });
};

export { clearStatusSurface, setStatusSurface };
export type { StatusSurfaceOptions, StatusSurfaceTone, StatusSurfaceVisibility };
