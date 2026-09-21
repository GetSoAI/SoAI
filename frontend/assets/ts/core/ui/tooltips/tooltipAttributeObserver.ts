/* SoAI - Shared UI tooltip attribute observer [frontend/assets/ts/core/ui/tooltips/tooltipAttributeObserver.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getMutationObserverCtor } from '@core/environment/public.ts';

interface TooltipAttributeObserverArguments {
    documentRef: Document;
    view: Window;
    attributeName: string;
    handleTarget(target: Element): void;
}

const createTooltipAttributeObserver = (inputArguments: TooltipAttributeObserverArguments): MutationObserver => {
    const MutationObserverCtor = getMutationObserverCtor();
    const observer = new MutationObserverCtor((mutations: MutationRecord[]) => {
        const handledTargets = new Set<Element>();
        for (const mutation of mutations) {
            if (mutation.type === 'attributes' && mutation.attributeName === inputArguments.attributeName && mutation.target instanceof Element && !handledTargets.has(mutation.target)) {
                handledTargets.add(mutation.target);
                inputArguments.handleTarget(mutation.target);
            }
        }
    });
    observer.observe(inputArguments.documentRef.documentElement, {
        attributes: true,
        attributeFilter: [inputArguments.attributeName],
        subtree: true
    });
    return observer;
};

export { createTooltipAttributeObserver };
