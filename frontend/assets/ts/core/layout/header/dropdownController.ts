/* SoAI - Shared layout dropdown controller [frontend/assets/ts/core/layout/header/dropdownController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { exitWithPresence, isPresenceExiting, prepareEnterWithPresence, requestPresenceEnter } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { drainCleanupStack } from '@core/lifecycle/cleanup.ts';

interface HeaderDropdownLifecycleHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
}

interface HeaderDropdownControllerOptions {
    host: HeaderDropdownLifecycleHost;
    dropdownId: string;
}

const setHeaderDropdownState = (button: HTMLElement | null, isOpen: boolean): void => {
    if (button) {
        dom.setAttribute(button, 'aria-expanded', isOpen ? 'true' : 'false');
    }
};

class HeaderDropdownController {
    readonly #host: HeaderDropdownLifecycleHost;
    readonly #dropdownId: string;
    #button: HTMLElement | null = null;
    #dropdown: HTMLElement | null = null;
    #isOpen = false;
    #cleanups: Array<() => void> = [];

    constructor(options: HeaderDropdownControllerOptions) {
        this.#host = options.host;
        this.#dropdownId = options.dropdownId;
    }

    attach(button: HTMLElement, dropdown: HTMLElement): void {
        this.reset();
        this.#button = button;
        this.#dropdown = dropdown;
        dropdown.setAttribute('data-presence', '');
        dropdown.setAttribute('data-presence-visual-only', '');
        dropdown.setAttribute('data-presence-atomic', '');
        this.#addCleanup(
            this.#host.on(dropdown, 'keydown', (event: Event) => {
                if (!(event instanceof KeyboardEvent) || event.key !== 'Escape') {
                    return;
                }
                event.stopPropagation();
                this.hide();
                this.requireButton().focus();
            })
        );
        this.#addCleanup(
            this.#host.on(dom.getDocument(), 'keydown', (event: Event) => {
                if (!this.#isOpen || !(event instanceof KeyboardEvent) || event.key !== 'Escape') {
                    return;
                }
                this.hide();
                this.requireButton().focus();
            })
        );
        setHeaderDropdownState(button, this.#isOpen);
    }

    reset(): void {
        if (this.#dropdown) {
            prepareEnterWithPresence(this.#dropdown, false)();
            this.#dropdown.classList.add('u-hidden');
            this.#dropdown.removeAttribute('data-presence-atomic');
            this.#dropdown.removeAttribute('data-presence');
            setHeaderDropdownState(this.#button, false);
        }
        drainCleanupStack(this.#cleanups, (runtimeError) => {
            errorHandler.warn('Header', 'Dropdown binding cleanup failed', runtimeError);
        });
        this.#button = null;
        this.#dropdown = null;
        this.#isOpen = false;
    }

    isOpen(): boolean {
        return this.#isOpen;
    }

    show(): void {
        if (this.#isOpen) return;
        const dropdown = this.requireDropdown();
        const reopening = isPresenceExiting(dropdown);
        const start = prepareEnterWithPresence(dropdown, reopening, true);
        if (!reopening) requestPresenceEnter(dropdown);
        dropdown.classList.remove('u-hidden');
        start();
        this.#isOpen = true;
        setHeaderDropdownState(this.#button, true);
    }

    hide(): void {
        const dropdown = this.#dropdown;
        if (dropdown && this.#isOpen) {
            exitWithPresence(dropdown, null, () => {
                dropdown.classList.add('u-hidden');
            });
        }
        this.#isOpen = false;
        setHeaderDropdownState(this.#button, false);
    }

    toggle(forceState: boolean | null = null): void {
        const shouldOpen = forceState === null ? !this.#isOpen : forceState;
        if (shouldOpen) {
            this.show();
            return;
        }
        this.hide();
    }

    private requireButton(): HTMLElement {
        if (!this.#button) {
            throw new Error(`Header dropdown "${this.#dropdownId}" button is unavailable`);
        }
        return this.#button;
    }

    private requireDropdown(): HTMLElement {
        if (!this.#dropdown) {
            throw new Error(`Header dropdown "${this.#dropdownId}" content is unavailable`);
        }
        return this.#dropdown;
    }

    #addCleanup(cleanup: (() => void) | void): void {
        if (typeof cleanup === 'function') {
            this.#cleanups.push(cleanup);
        }
    }
}

export { HeaderDropdownController, setHeaderDropdownState };
export type { HeaderDropdownLifecycleHost };
