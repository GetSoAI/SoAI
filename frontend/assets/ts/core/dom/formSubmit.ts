/* SoAI - Shared DOM form submit [frontend/assets/ts/core/dom/formSubmit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface BoundFormSubmitEvent {
    event: Event;
    form: HTMLFormElement;
}

interface FormSubmitBindingOptions {
    root: HTMLElement;
    signal: AbortSignal;
    form?: HTMLFormElement | undefined;
    formId?: string | undefined;
    capture?: boolean | undefined;
    preventDefault?: boolean | undefined;
    onSubmit: (submitEvent: BoundFormSubmitEvent) => void;
}

const resolveSubmittedForm = (event: Event, options: FormSubmitBindingOptions): HTMLFormElement | null => {
    const target = event.target;
    if (!(target instanceof HTMLFormElement)) {
        return null;
    }
    if (!options.root.contains(target)) {
        return null;
    }
    if (options.form !== undefined && target !== options.form) {
        return null;
    }
    if (options.formId !== undefined && target.id !== options.formId) {
        return null;
    }
    return target;
};

const bindFormSubmit = (options: FormSubmitBindingOptions): void => {
    options.root.addEventListener(
        'submit',
        (event: Event): void => {
            const form = resolveSubmittedForm(event, options);
            if (!form) {
                return;
            }
            if (options.preventDefault === true) {
                event.preventDefault();
            }
            options.onSubmit({ event, form });
        },
        { signal: options.signal, capture: options.capture === true }
    );
};

export { bindFormSubmit };
export type { BoundFormSubmitEvent, FormSubmitBindingOptions };
