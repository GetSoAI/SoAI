/* SoAI - Interface scale preference domain [frontend/assets/ts/core/layout/interfaceScale.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isDocument } from '@core/dom/domEnvironment.ts';
import { dispatchCustomEvent, getDocumentElement } from '@core/environment/public.ts';

type InterfaceScalePercent = 50 | 75 | 100 | 125 | 150;
type InterfaceScaleAttributeWriter = (name: string, value: string) => void;

const INTERFACE_SCALE_ATTRIBUTE = 'data-interface-scale';
const INTERFACE_SCALE_STORAGE_KEY = 'soai.ui.interface_scale';
const INTERFACE_SCALE_CHANGED_EVENT = 'soai:interface-scale:changed';
const INTERFACE_SCALE_PERCENT_STEPS: readonly InterfaceScalePercent[] = Object.freeze([50, 75, 100, 125, 150]);
const INTERFACE_SCALE_MIN_PERCENT: InterfaceScalePercent = 50;
const INTERFACE_SCALE_MAX_PERCENT: InterfaceScalePercent = 150;
const INTERFACE_SCALE_STEP_PERCENT = 25;
const DEFAULT_INTERFACE_SCALE_PERCENT: InterfaceScalePercent = 100;

const isInterfaceScalePercent = <Value>(value: Value): value is Value & InterfaceScalePercent => INTERFACE_SCALE_PERCENT_STEPS.some((step) => step === value);

const resolveInterfaceScalePercent = <Value>(value: Value): InterfaceScalePercent => (isInterfaceScalePercent(value) ? value : DEFAULT_INTERFACE_SCALE_PERCENT);

const resolveInterfaceScalePercentFromRoot = (root: Element): InterfaceScalePercent => {
    const attributeValue = root.getAttribute(INTERFACE_SCALE_ATTRIBUTE);
    const numericValue = attributeValue === null ? null : Number(attributeValue);
    return resolveInterfaceScalePercent(numericValue);
};

const resolveInterfaceScaleDocument = (scope: Document | Element | null | undefined): Document => {
    if (!scope) {
        return getDocumentElement().ownerDocument;
    }
    return isDocument(scope) ? scope : scope.ownerDocument;
};

const resolveInterfaceScalePercentFromScope = (scope: Document | Element | null | undefined): InterfaceScalePercent => {
    return resolveInterfaceScalePercentFromRoot(resolveInterfaceScaleDocument(scope).documentElement);
};

const interfaceScaleFactorFromRoot = (root: Element): number => resolveInterfaceScalePercentFromRoot(root) / 100;

const interfaceScaleFactorFromScope = (scope: Document | Element | null | undefined): number => resolveInterfaceScalePercentFromScope(scope) / 100;

const applyInterfaceScaleAttribute = (root: Element, percent: InterfaceScalePercent, writeAttribute: InterfaceScaleAttributeWriter): boolean => {
    if (!isInterfaceScalePercent(percent)) {
        throw new TypeError('Interface scale must be one of the supported percentage steps');
    }
    const previousPercent = resolveInterfaceScalePercentFromRoot(root);
    writeAttribute(INTERFACE_SCALE_ATTRIBUTE, String(percent));
    return previousPercent !== percent;
};

const dispatchInterfaceScaleChanged = (percent: InterfaceScalePercent): void => {
    dispatchCustomEvent(INTERFACE_SCALE_CHANGED_EVENT, { percent });
};

export { DEFAULT_INTERFACE_SCALE_PERCENT, INTERFACE_SCALE_ATTRIBUTE, INTERFACE_SCALE_CHANGED_EVENT, INTERFACE_SCALE_MAX_PERCENT, INTERFACE_SCALE_MIN_PERCENT, INTERFACE_SCALE_PERCENT_STEPS, INTERFACE_SCALE_STEP_PERCENT, INTERFACE_SCALE_STORAGE_KEY, applyInterfaceScaleAttribute, dispatchInterfaceScaleChanged, interfaceScaleFactorFromRoot, interfaceScaleFactorFromScope, isInterfaceScalePercent, resolveInterfaceScalePercent, resolveInterfaceScalePercentFromRoot };
export type { InterfaceScalePercent };
