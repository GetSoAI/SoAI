/* SoAI - Shared UI controller [frontend/assets/ts/core/ui/inlineedit/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';

interface InlineTextEditElements {
    trigger: HTMLElement;
    input: HTMLInputElement;
    saveButton: HTMLButtonElement;
}

interface InlineTextEditControllerOptions {
    elements: InlineTextEditElements;
    readValue: () => string;
    normalizeValue: (value: string) => string;
    save: (value: string) => Promise<void>;
    handleSaveError: (error: Error) => void;
}

type InlineTextEditKeyAction = 'save' | 'cancel' | null;

const focusAndSelectInlineTextEditInput = (input: HTMLInputElement): void => {
    input.focus();
    input.select();
};

const resolveInlineTextEditKeyAction = (event: KeyboardEvent): InlineTextEditKeyAction => {
    if (event.key === 'Enter') {
        event.preventDefault();
        return 'save';
    }
    if (event.key === 'Escape') {
        event.preventDefault();
        return 'cancel';
    }
    return null;
};

const shouldKeepInlineTextEditOpenOnBlur = (event: FocusEvent, saveButton: HTMLButtonElement): boolean => event.relatedTarget === saveButton;

const syncInlineTextEditElements = (elements: InlineTextEditElements, editing: boolean, pending: boolean): void => {
    elements.trigger.classList.toggle('u-hidden', editing);
    elements.input.classList.toggle('u-hidden', !editing);
    elements.saveButton.classList.toggle('u-hidden', !editing);
    elements.input.disabled = pending;
    elements.saveButton.disabled = pending;
};

class InlineTextEditController {
    readonly #elements: InlineTextEditElements;
    readonly #readValue: () => string;
    readonly #normalizeValue: (value: string) => string;
    readonly #save: (value: string) => Promise<void>;
    readonly #handleSaveError: (error: Error) => void;
    #editing = false;
    #pending = false;
    #disposed = false;

    constructor(options: InlineTextEditControllerOptions) {
        this.#elements = options.elements;
        this.#readValue = options.readValue;
        this.#normalizeValue = options.normalizeValue;
        this.#save = options.save;
        this.#handleSaveError = options.handleSaveError;
        this.#sync();
    }

    isTarget(target: EventTarget | null): boolean {
        return target === this.#elements.input;
    }

    start(): void {
        if (this.#disposed || this.#pending || this.#editing) {
            return;
        }
        this.#editing = true;
        this.#elements.input.value = this.#readValue();
        this.#sync();
        focusAndSelectInlineTextEditInput(this.#elements.input);
    }

    handleInput(): void {
        if (!this.#editing || this.#disposed) {
            return;
        }
        const normalizedValue = this.#normalizeValue(this.#elements.input.value);
        if (this.#elements.input.value !== normalizedValue) {
            this.#elements.input.value = normalizedValue;
        }
    }

    handleKeydown(event: KeyboardEvent): boolean {
        if (!this.#editing || this.#disposed) {
            return false;
        }
        const action = resolveInlineTextEditKeyAction(event);
        if (action === 'save') {
            void this.save().catch((error) => {
                this.#handleSaveError(ensureError(error));
            });
            return true;
        }
        if (action === 'cancel') {
            this.cancel();
            return true;
        }
        return false;
    }

    handleBlur(event: FocusEvent): void {
        if (!this.#editing || this.#pending || this.#disposed || shouldKeepInlineTextEditOpenOnBlur(event, this.#elements.saveButton)) {
            return;
        }
        this.cancel();
    }

    async save(): Promise<void> {
        if (!this.#editing || this.#pending || this.#disposed) {
            return;
        }
        const value = this.#normalizeValue(this.#elements.input.value);
        this.#elements.input.value = value;
        this.#pending = true;
        this.#sync();
        try {
            await this.#save(value);
            if (this.#disposed) {
                return;
            }
            this.#editing = false;
        } catch (error) {
            this.#handleSaveError(ensureError(error));
        } finally {
            this.#pending = false;
            if (!this.#disposed) {
                this.#sync();
                if (this.#editing) {
                    focusAndSelectInlineTextEditInput(this.#elements.input);
                }
            }
        }
    }

    cancel(): void {
        if (!this.#editing || this.#pending || this.#disposed) {
            return;
        }
        this.#editing = false;
        this.#elements.input.value = this.#readValue();
        this.#sync();
        this.#elements.trigger.focus();
    }

    dispose(): void {
        this.#disposed = true;
        this.#editing = false;
        this.#pending = false;
    }

    #sync(): void {
        syncInlineTextEditElements(this.#elements, this.#editing, this.#pending);
    }
}

export { focusAndSelectInlineTextEditInput, InlineTextEditController, resolveInlineTextEditKeyAction, shouldKeepInlineTextEditOpenOnBlur, syncInlineTextEditElements };
export type { InlineTextEditControllerOptions, InlineTextEditElements, InlineTextEditKeyAction };
