/* SoAI - Automation editor loading, failure, conflict, and freeze presentation [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationEditorStatusController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiSelector } from '@core/modals/uiIds.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';

type AutomationEditorFreezeReason = 'loading' | 'saving';

type AutomationEditorPrerequisitesState = { type: 'loading' } | { type: 'ready' } | { type: 'failed'; message: string; retryable: boolean };

interface AutomationEditorStatusControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modal: HTMLElement;
    formRegion: HTMLElement;
}

class AutomationEditorStatusController {
    readonly #formRegion: HTMLElement;
    readonly #loading: HTMLElement;
    readonly #prerequisitesError: HTMLElement;
    readonly #prerequisitesErrorMessage: HTMLElement;
    readonly #prerequisitesRetry: HTMLElement;
    readonly #toolsUnavailable: HTMLElement;
    readonly #conflict: HTMLElement;
    readonly #conflictMessage: HTMLElement;
    readonly #freezeReasons = new Set<AutomationEditorFreezeReason>();
    #prerequisitesState: AutomationEditorPrerequisitesState = { type: 'ready' };
    #hasReadyDraft = false;
    #focusBeforeFreeze: HTMLElement | null = null;

    constructor(dependencies: AutomationEditorStatusControllerDependencies) {
        const modal = dependencies.modal;
        const requireElement = (token: string): HTMLElement => dependencies.requireHTMLElement(modalUiSelector(modal.id, token), modal);
        this.#formRegion = dependencies.formRegion;
        this.#loading = requireElement('prerequisites-loading');
        this.#prerequisitesError = requireElement('prerequisites-error');
        this.#prerequisitesErrorMessage = requireElement('prerequisites-error-message');
        this.#prerequisitesRetry = requireElement('prerequisites-retry');
        this.#toolsUnavailable = requireElement('tools-unavailable');
        this.#conflict = requireElement('conflict');
        this.#conflictMessage = requireElement('conflict-message');
    }

    reset(): void {
        this.setPrerequisitesState({ type: 'ready' });
        this.#hasReadyDraft = false;
        this.#freezeReasons.clear();
        this.#applyFreeze();
        this.setToolsUnavailable(false);
        this.showConflict(null);
    }

    setPrerequisitesState(state: AutomationEditorPrerequisitesState): void {
        this.#prerequisitesState = state;
        if (state.type === 'ready') this.#hasReadyDraft = true;
        const formHidden = state.type === 'loading' || (state.type === 'failed' && !this.#hasReadyDraft);
        this.#formRegion.classList.toggle('u-hidden', formHidden);
        this.#formRegion.setAttribute('aria-hidden', String(formHidden));
        this.#loading.classList.toggle('u-hidden', state.type !== 'loading');
        this.#prerequisitesErrorMessage.textContent = state.type === 'failed' ? state.message : '';
        this.#prerequisitesError.classList.toggle('u-hidden', state.type !== 'failed');
        this.#prerequisitesRetry.classList.toggle('u-hidden', state.type !== 'failed' || !state.retryable);
        this.setFrozen('loading', state.type !== 'ready');
    }

    arePrerequisitesReady(): boolean {
        return this.#prerequisitesState.type === 'ready';
    }

    setToolsUnavailable(unavailable: boolean): void {
        this.#toolsUnavailable.classList.toggle('u-hidden', !unavailable);
    }

    showConflict(message: string | null): void {
        this.#conflictMessage.textContent = message ?? '';
        this.#conflict.classList.toggle('u-hidden', message === null);
    }

    setFrozen(reason: AutomationEditorFreezeReason, frozen: boolean): void {
        if (frozen) {
            this.#freezeReasons.add(reason);
        } else {
            this.#freezeReasons.delete(reason);
        }
        this.#applyFreeze();
    }

    #applyFreeze(): void {
        const frozen = this.#freezeReasons.size > 0;
        if (frozen === this.#formRegion.inert) {
            return;
        }
        if (frozen) {
            const active = this.#formRegion.ownerDocument.activeElement;
            this.#focusBeforeFreeze = active instanceof HTMLElement && this.#formRegion.contains(active) ? active : null;
            this.#formRegion.inert = true;
            setAriaBusy(this.#formRegion, true);
            return;
        }
        this.#formRegion.inert = false;
        setAriaBusy(this.#formRegion, false);
        const focusTarget = this.#focusBeforeFreeze;
        this.#focusBeforeFreeze = null;
        if (focusTarget?.isConnected) {
            focusTarget.focus({ preventScroll: true });
        }
    }
}

export { AutomationEditorStatusController };
export type { AutomationEditorFreezeReason, AutomationEditorPrerequisitesState };
