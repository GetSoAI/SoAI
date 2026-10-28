/* SoAI - Shared progress width synchronization helpers [frontend/assets/ts/core/ui/progressWidths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { DOMQueryRoot } from '@core/dom/types.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { resolveProgressColor } from '@core/ui/progressColors.ts';

const PROGRESS_WIDTH_ATTRIBUTE = 'data-soai-progress-width';

interface DeterminateProgressSyncOptions {
    fillElement: Element;
    progress: number;
    progressbarElement?: Element | null | undefined;
    valueElement?: Element | null | undefined;
    colorize?: boolean | undefined;
    setStyle?: ((element: Element, property: string, value: string) => void) | undefined;
    setText?: ((element: Element, value: string) => void) | undefined;
    setAttribute?: ((element: Element, name: string, value: string) => void) | undefined;
}

const syncDeterminateProgress = (options: DeterminateProgressSyncOptions): number => {
    const progress = clampPercent(options.progress);
    const progressText = `${Math.round(progress)}%`;
    const setStyle = options.setStyle ?? ((element: Element, property: string, value: string): void => dom.setStyle(element, property, value));
    const setText = options.setText ?? ((element: Element, value: string): void => dom.setText(element, value));
    const setAttribute = options.setAttribute ?? ((element: Element, name: string, value: string): void => dom.setAttribute(element, name, value));
    setStyle(options.fillElement, 'width', `${progress}%`);
    if (options.colorize === true) {
        setStyle(options.fillElement, '--soai-progress-color', resolveProgressColor(progress));
    }
    if (options.valueElement) {
        setText(options.valueElement, progressText);
    }
    if (options.progressbarElement) {
        setAttribute(options.progressbarElement, 'aria-valuenow', String(Math.round(progress)));
    }
    return progress;
};

const readProgressWidth = (element: HTMLElement): number | null => {
    const rawValue = element.getAttribute(PROGRESS_WIDTH_ATTRIBUTE);
    if (!rawValue) {
        return null;
    }
    const numericValue = Number(rawValue);
    if (!Number.isFinite(numericValue)) {
        throw new TypeError(`Progress width must be numeric: ${rawValue}`);
    }
    return clampPercent(numericValue);
};

const applyProgressWidths = (root: DOMQueryRoot, updateStyle: (element: Element, property: string, value: string | null) => void): void => {
    const progressElements = dom.resolveAll(`[${PROGRESS_WIDTH_ATTRIBUTE}]`, root);
    for (const progressElement of progressElements) {
        if (!(progressElement instanceof HTMLElement)) {
            throw new TypeError('Progress width target must be an HTMLElement');
        }
        const progress = readProgressWidth(progressElement);
        if (progress === null) {
            updateStyle(progressElement, 'width', null);
            updateStyle(progressElement, '--soai-progress-color', null);
        } else {
            syncDeterminateProgress({ fillElement: progressElement, progress, colorize: true, setStyle: updateStyle });
        }
    }
};

export { applyProgressWidths, PROGRESS_WIDTH_ATTRIBUTE, syncDeterminateProgress };
