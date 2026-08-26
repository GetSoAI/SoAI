/* SoAI - SaveScope automatic dirty and keyboard-save event binding [frontend/assets/ts/core/save/autoNotifyBinding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { SaveScope } from '@core/save/contracts.ts';

type SaveAutoNotifyBindingOptions = {
    scope: SaveScope;
    headerContextId: string;
    signal: AbortSignal;
    autoNotifyRoot: Element | null | undefined;
    autoNotifyAdditionalRoots: readonly Element[] | undefined;
    additionalDirtyEventNames: readonly string[];
    requestSave: (context: string) => Promise<void>;
    sync: () => void;
};

const NON_TEXT_INPUT_TYPES = new Set(['button', 'checkbox', 'color', 'date', 'datetime-local', 'file', 'hidden', 'image', 'month', 'radio', 'range', 'reset', 'submit', 'time', 'week']);

const appendUniqueRoot = (roots: Element[], root: Element | null | undefined): void => {
    if (root && !roots.includes(root)) {
        roots.push(root);
    }
};

const isTextInputTarget = (target: EventTarget | null): boolean => {
    const element = target instanceof Element ? target : null;
    if (!element) {
        return false;
    }
    if (element instanceof HTMLElement && element.isContentEditable) {
        return true;
    }
    if (element instanceof HTMLTextAreaElement) {
        return true;
    }
    if (!(element instanceof HTMLInputElement) || element.disabled || element.readOnly) {
        return false;
    }
    const inputType = element.type.trim().toLowerCase();
    return !NON_TEXT_INPUT_TYPES.has(inputType);
};

const createKeyboardSaveHandler = (options: SaveAutoNotifyBindingOptions): ((event: Event) => void) => {
    return (event: Event): void => {
        if (!(event instanceof KeyboardEvent) || event.defaultPrevented) {
            return;
        }
        if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey) || event.isComposing) {
            return;
        }
        if (!isTextInputTarget(event.target) || !options.scope.canSave()) {
            return;
        }
        event.preventDefault();
        terminateHandledPromise(options.requestSave(`Keyboard save (${options.headerContextId})`));
        options.sync();
    };
};

const connectSaveAutoNotify = (options: SaveAutoNotifyBindingOptions): void => {
    const roots: Element[] = [];
    appendUniqueRoot(roots, options.autoNotifyRoot);
    for (const root of options.autoNotifyAdditionalRoots ?? []) {
        appendUniqueRoot(roots, root);
    }
    const notify = (): void => options.scope.notifyChanged();
    const handleKeyboardSave = createKeyboardSaveHandler(options);
    for (const root of roots) {
        root.addEventListener('input', notify, { signal: options.signal, capture: true });
        root.addEventListener('change', notify, { signal: options.signal, capture: true });
        root.addEventListener('core.modal.open', notify, { signal: options.signal });
        root.addEventListener('core.modal.close', notify, { signal: options.signal });
        root.addEventListener('keydown', handleKeyboardSave, { signal: options.signal });
        for (const eventName of options.additionalDirtyEventNames) {
            root.addEventListener(eventName, notify, { signal: options.signal });
        }
    }
};

export { connectSaveAutoNotify };
