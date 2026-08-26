/* SoAI - Shared DOM data action [frontend/assets/ts/core/dom/dataAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const ACTION_ELEMENT_SELECTOR = '[data-action]';

type ActionDataset = DOMStringMap & { action: string };

const hasDataAction = (dataset: DOMStringMap): dataset is ActionDataset => {
    return typeof dataset === 'object' && dataset !== null && typeof dataset.action === 'string';
};

type ElementWithActionDataset = HTMLElement & { dataset: ActionDataset };
type TypedDataActionResult<TAction extends string> = { action: TAction; actionElement: ElementWithActionDataset };
type DelegatedActionResolveResult = { type: 'action'; actionElement: ElementWithActionDataset } | { type: 'ignored' } | { type: 'miss' };

export const hasDataActionElement = (element: HTMLElement): element is ElementWithActionDataset => {
    return hasDataAction(element.dataset);
};

const assertRootDataActionsAreKnown = <TAction extends string>(root: Element, label: string, isAction: (value: string | undefined) => value is TAction): void => {
    const actionElements = root.querySelectorAll('[data-action]');
    if (actionElements.length === 0) {
        throw new Error(`${label} missing data-action elements`);
    }
    for (const actionElement of actionElements) {
        if (!(actionElement instanceof HTMLElement) || !hasDataActionElement(actionElement)) {
            throw new Error(`${label} contains invalid data-action element`);
        }
        if (!isAction(actionElement.dataset.action)) {
            throw new Error(`${label} contains unknown data-action "${actionElement.dataset.action}"`);
        }
    }
};

function resolveDataActionElement(target: EventTarget | null, root: Element): ElementWithActionDataset | null;
function resolveDataActionElement<TAction extends string>(target: EventTarget | null, root: Element, isAction: (value: string | undefined) => value is TAction): TypedDataActionResult<TAction> | null;
function resolveDataActionElement<TAction extends string>(target: EventTarget | null, root: Element, isAction?: (value: string | undefined) => value is TAction): ElementWithActionDataset | TypedDataActionResult<TAction> | null {
    if (!(target instanceof Element)) return null;
    const candidate = target.closest(ACTION_ELEMENT_SELECTOR);
    if (!(candidate instanceof HTMLElement)) return null;
    if (!root.contains(candidate)) return null;
    if (!hasDataActionElement(candidate)) return null;
    if (!isAction) return candidate;
    const action = candidate.dataset.action;
    if (!isAction(action)) return null;
    return { action, actionElement: candidate };
}

export const shouldPreventDefaultForActionElement = (element: HTMLElement): boolean => {
    if (element instanceof HTMLAnchorElement) {
        return true;
    }
    if (element instanceof HTMLButtonElement) {
        if (!element.form) {
            return false;
        }
        const normalized = element.type.trim().toLowerCase();
        return normalized === 'submit' || normalized === 'reset';
    }
    if (element instanceof HTMLInputElement) {
        if (!element.form) {
            return false;
        }
        const normalized = element.type.trim().toLowerCase();
        return normalized === 'submit' || normalized === 'reset' || normalized === 'image';
    }
    return false;
};

type DelegatedActionPreventDefaultMode = 'always' | 'click-always-except-checkbox' | 'interactive' | 'never';
type DelegatedActionMouseButtonMode = 'any' | 'primary';

interface DelegatedActionEvent<TAction extends string> {
    event: Event;
    action: TAction;
    actionElement: ElementWithActionDataset;
}

type DelegatedActionHandler<TAction extends string, TResult = void> = (actionEvent: DelegatedActionEvent<TAction>) => TResult;

interface DelegatedActionHandlerOptions<TAction extends string, TResult = void> {
    root: Element;
    isAction: (value: string | undefined) => value is TAction;
    onAction: DelegatedActionHandler<TAction, TResult>;
    preventDefault?: DelegatedActionPreventDefaultMode;
    stopPropagation?: boolean;
    mouseButton?: DelegatedActionMouseButtonMode;
    ignoreDisabled?: boolean;
    ignorePrevented?: boolean;
    ignoreFormControls?: boolean;
    disabledAttributes?: readonly string[];
}

interface DelegatedActionResolveOptions {
    root: Element;
    event: Event;
    preventDefault?: DelegatedActionPreventDefaultMode;
    stopPropagation?: boolean;
    mouseButton?: DelegatedActionMouseButtonMode;
    ignoreDisabled?: boolean;
    ignoreFormControls?: boolean;
    disabledAttributes?: readonly string[];
}

const isFileInputActivationElement = (element: Element): boolean => {
    if (element instanceof HTMLInputElement && element.type === 'file') {
        return true;
    }
    if (element instanceof HTMLLabelElement) {
        const controlId = element.htmlFor;
        const control = controlId ? element.ownerDocument.getElementById(controlId) : null;
        return control instanceof HTMLInputElement && control.type === 'file';
    }
    return false;
};

const shouldPreventDefaultForDelegatedActionElement = (element: Element): boolean => {
    if (isFileInputActivationElement(element)) {
        return false;
    }
    if (element instanceof HTMLElement) {
        return shouldPreventDefaultForActionElement(element);
    }
    return true;
};

const shouldPreventDefaultExceptFileActionElement = (element: Element): boolean => {
    return !isFileInputActivationElement(element);
};

const isDisabledActionElement = (element: Element, disabledAttributes: readonly string[] = []): boolean => {
    if (element instanceof HTMLButtonElement || element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) {
        return element.disabled;
    }
    if (element instanceof HTMLElement) {
        if (element.getAttribute('aria-disabled') === 'true') {
            return true;
        }
        return disabledAttributes.some((attribute) => element.getAttribute(attribute) === 'true');
    }
    return false;
};

const isFormControlActionElement = (element: Element): boolean => {
    return element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement;
};

const isCheckboxActionClick = (event: Event, element: Element): boolean => {
    return event.type === 'click' && element instanceof HTMLInputElement && element.type === 'checkbox';
};

const shouldPreventDefaultForMode = (event: Event, element: Element, mode: DelegatedActionPreventDefaultMode): boolean => {
    if (mode === 'never') {
        return false;
    }
    if (mode === 'click-always-except-checkbox') {
        return event.type === 'click' && !isCheckboxActionClick(event, element);
    }
    if (mode === 'always') {
        return true;
    }
    return shouldPreventDefaultForDelegatedActionElement(element);
};

const isAllowedDelegatedActionMouseEvent = (event: Event, mouseButton: DelegatedActionMouseButtonMode): boolean => {
    if (mouseButton !== 'primary' || !(event instanceof MouseEvent)) {
        return true;
    }
    return event.button === 0;
};

const applyDelegatedActionEventDefaults = (event: Event, element: Element, mode: DelegatedActionPreventDefaultMode, stopPropagation: boolean): void => {
    if (shouldPreventDefaultForMode(event, element, mode)) {
        event.preventDefault();
    }
    if (stopPropagation) {
        event.stopPropagation();
    }
};

const resolveDelegatedActionElementResult = (options: DelegatedActionResolveOptions): DelegatedActionResolveResult => {
    if (!isAllowedDelegatedActionMouseEvent(options.event, options.mouseButton ?? 'any')) {
        return { type: 'ignored' };
    }
    const actionElement = resolveDataActionElement(options.event.target, options.root);
    if (!actionElement) {
        return { type: 'miss' };
    }
    if (options.ignoreFormControls === true && isFormControlActionElement(actionElement)) {
        return { type: 'ignored' };
    }
    if (options.ignoreDisabled === true && isDisabledActionElement(actionElement, options.disabledAttributes ?? [])) {
        return { type: 'ignored' };
    }
    applyDelegatedActionEventDefaults(options.event, actionElement, options.preventDefault ?? 'interactive', options.stopPropagation === true);
    return { type: 'action', actionElement };
};

const resolveDelegatedActionElement = (options: DelegatedActionResolveOptions): ElementWithActionDataset | null => {
    const result = resolveDelegatedActionElementResult(options);
    if (result.type !== 'action') {
        return null;
    }
    return result.actionElement;
};

const handleDelegatedActionEvent = <TAction extends string, TResult = void>(event: Event, options: DelegatedActionHandlerOptions<TAction, TResult>): TResult | null => {
    if (options.ignorePrevented === true && event.defaultPrevented) {
        return null;
    }
    if (!isAllowedDelegatedActionMouseEvent(event, options.mouseButton ?? 'any')) {
        return null;
    }
    const resolved = resolveDataActionElement(event.target, options.root, options.isAction);
    if (!resolved) {
        return null;
    }
    if (options.ignoreFormControls === true && isFormControlActionElement(resolved.actionElement)) {
        return null;
    }
    if (options.ignoreDisabled === true && isDisabledActionElement(resolved.actionElement, options.disabledAttributes ?? [])) {
        return null;
    }
    applyDelegatedActionEventDefaults(event, resolved.actionElement, options.preventDefault ?? 'interactive', options.stopPropagation === true);
    return options.onAction({
        event,
        action: resolved.action,
        actionElement: resolved.actionElement
    });
};

const assertElementDataAction = (element: Element, action: string, label: string): void => {
    if (element.getAttribute('data-action') !== action) {
        throw new Error(`${label} requires data-action="${action}"`);
    }
};

export { assertElementDataAction, assertRootDataActionsAreKnown, handleDelegatedActionEvent, resolveDelegatedActionElement, resolveDelegatedActionElementResult, shouldPreventDefaultExceptFileActionElement, shouldPreventDefaultForDelegatedActionElement };
export type { DelegatedActionMouseButtonMode, DelegatedActionPreventDefaultMode, DelegatedActionResolveResult, ElementWithActionDataset };
