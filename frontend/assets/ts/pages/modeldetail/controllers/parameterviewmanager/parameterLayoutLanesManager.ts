/* SoAI - Parameter layout lane management [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/parameterLayoutLanesManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { PARAMETERS_LAYOUT_SELECTOR } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';

const PARAMETER_LAYOUT_LANE_CLASS = 'model-parameter-lane';
const PARAMETER_SECTION_SELECTOR = '.model-parameter-section';
const PARAMETER_LANE_MIN_WIDTH_FALLBACK = 520;

const requireHTMLElement = (element: Element): HTMLElement => {
    if (element instanceof HTMLElement) {
        return element;
    }
    throw new TypeError('Model detail parameter lane children must be HTMLElements');
};

const readPixelValue = (value: string, fallback: number): number => {
    const parsed = Number.parseFloat(value.trim());
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const readSectionIndex = (section: HTMLElement): number => {
    const index = Number(section.dataset['parameterLayoutIndex']);
    return Number.isInteger(index) && index >= 0 ? index : 0;
};

const assignSectionIndexes = (sections: HTMLElement[]): void => {
    sections.forEach((section, index) => {
        const current = Number(section.dataset['parameterLayoutIndex']);
        if (!Number.isInteger(current) || current < 0) {
            section.dataset['parameterLayoutIndex'] = String(index);
        }
    });
};

const collectParameterSections = (layout: HTMLElement): HTMLElement[] => {
    const sections: HTMLElement[] = [];
    dom.resolveAll(PARAMETER_SECTION_SELECTOR, layout).forEach((element) => {
        const section = requireHTMLElement(element);
        if (section.parentElement === layout || section.parentElement?.classList.contains(PARAMETER_LAYOUT_LANE_CLASS)) {
            sections.push(section);
        }
    });
    assignSectionIndexes(sections);
    return sections.sort((left, right) => readSectionIndex(left) - readSectionIndex(right));
};

const resolveLaneCount = (layout: HTMLElement): number => {
    const style = getComputedStyle(layout);
    const laneMinWidth = readPixelValue(style.getPropertyValue('--model-parameter-lane-min-width'), PARAMETER_LANE_MIN_WIDTH_FALLBACK);
    const gap = readPixelValue(style.columnGap, 0);
    const width = measureLayoutBox(layout).width;
    if (width <= laneMinWidth) {
        return 1;
    }
    return Math.max(1, Math.floor((width + gap) / (laneMinWidth + gap)));
};

const createLane = (layout: HTMLElement, index: number): HTMLElement => {
    const lane = layout.ownerDocument.createElement('div');
    lane.className = PARAMETER_LAYOUT_LANE_CLASS;
    lane.dataset['parameterLane'] = String(index);
    return lane;
};

const isLayoutArrangedForLaneCount = (layout: HTMLElement, laneCount: number): boolean => {
    let laneElements = 0;
    for (const child of Array.from(layout.children)) {
        if (child instanceof HTMLElement && child.classList.contains(PARAMETER_LAYOUT_LANE_CLASS)) {
            laneElements += 1;
            continue;
        }
        return false;
    }
    return laneElements === laneCount;
};

const arrangeParameterLayoutLanes = (layout: HTMLElement): void => {
    const laneCount = resolveLaneCount(layout);
    if (isLayoutArrangedForLaneCount(layout, laneCount)) {
        return;
    }
    const sections = collectParameterSections(layout);
    if (!sections.length) {
        return;
    }
    const lanes: HTMLElement[] = [];
    for (let index = 0; index < laneCount; index += 1) {
        lanes.push(createLane(layout, index));
    }
    sections.forEach((section, index) => {
        const lane = lanes[index % laneCount];
        if (!lane) {
            throw new Error('Model detail parameter lane resolution failed');
        }
        lane.append(section);
    });
    layout.replaceChildren(...lanes);
};

const bindParameterLayoutLanes = (container: Element): (() => void) => {
    const layoutElement = dom.resolve(PARAMETERS_LAYOUT_SELECTOR, container);
    if (!(layoutElement instanceof HTMLElement)) {
        return () => undefined;
    }
    arrangeParameterLayoutLanes(layoutElement);
    const view = layoutElement.ownerDocument.defaultView;
    if (!view || typeof ResizeObserver === 'undefined') {
        return () => undefined;
    }
    let frameId = 0;
    const observer = new ResizeObserver(() => {
        if (frameId) {
            view.cancelAnimationFrame(frameId);
        }
        frameId = view.requestAnimationFrame(() => {
            frameId = 0;
            arrangeParameterLayoutLanes(layoutElement);
        });
    });
    observer.observe(layoutElement);
    return () => {
        if (frameId) {
            view.cancelAnimationFrame(frameId);
            frameId = 0;
        }
        observer.disconnect();
    };
};

export { bindParameterLayoutLanes };
