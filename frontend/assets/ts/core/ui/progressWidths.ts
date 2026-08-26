/* SoAI - Shared progress width synchronization helpers [frontend/assets/ts/core/ui/progressWidths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { DOMQueryRoot } from '@core/dom/types.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';

const PROGRESS_WIDTH_ATTRIBUTE = 'data-soai-progress-width';

type ProgressUsageClass = 'progress-red' | 'progress-orange' | 'progress-yellow' | 'progress-green';

const PROGRESS_USAGE_CLASSES: readonly ProgressUsageClass[] = Object.freeze(['progress-red', 'progress-orange', 'progress-yellow', 'progress-green']);

const resolveProgressUsageClass = (percentUsed: number): ProgressUsageClass => {
    const normalizedPercent = clampPercent(percentUsed);
    if (normalizedPercent < 25) {
        return 'progress-red';
    }
    if (normalizedPercent < 50) {
        return 'progress-orange';
    }
    if (normalizedPercent < 75) {
        return 'progress-yellow';
    }
    return 'progress-green';
};

const syncProgressUsageClass = (element: Element, percentUsed: number): void => {
    element.classList.remove(...PROGRESS_USAGE_CLASSES);
    element.classList.add(resolveProgressUsageClass(percentUsed));
};

interface DeterminateProgressSyncOptions {
    fillElement: Element;
    progress: number;
    progressbarElement?: Element | null | undefined;
    valueElement?: Element | null | undefined;
    syncUsageClass?: boolean | undefined;
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
    if (options.syncUsageClass === true) {
        syncProgressUsageClass(options.fillElement, progress);
    }
    if (options.valueElement) {
        setText(options.valueElement, progressText);
    }
    if (options.progressbarElement) {
        setAttribute(options.progressbarElement, 'aria-valuenow', String(Math.round(progress)));
    }
    return progress;
};

const readProgressWidth = (element: HTMLElement): string | null => {
    const rawValue = element.getAttribute(PROGRESS_WIDTH_ATTRIBUTE);
    if (!rawValue) {
        return null;
    }
    const numericValue = Number(rawValue);
    if (!Number.isFinite(numericValue)) {
        throw new TypeError(`Progress width must be numeric: ${rawValue}`);
    }
    const clampedValue = clampPercent(numericValue);
    return `${clampedValue}%`;
};

const applyProgressWidths = (root: DOMQueryRoot, updateStyle: (element: Element, property: string, value: string | null) => void): void => {
    const progressElements = dom.resolveAll(`[${PROGRESS_WIDTH_ATTRIBUTE}]`, root);
    for (const progressElement of progressElements) {
        if (!(progressElement instanceof HTMLElement)) {
            throw new TypeError('Progress width target must be an HTMLElement');
        }
        updateStyle(progressElement, 'width', readProgressWidth(progressElement));
    }
};

export { applyProgressWidths, PROGRESS_WIDTH_ATTRIBUTE, resolveProgressUsageClass, syncDeterminateProgress };
