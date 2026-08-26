/* SoAI - License/Credits modal definitions registered by app bootstrap [frontend/assets/ts/core/licenseservice/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalBinder, ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { TEXT_MODAL_CONFIGS, TEXT_MODAL_KEYS } from '@core/licenseservice/constants.ts';
import { createTextModalElement, resolveTextModalButtons } from '@core/licenseservice/dom.ts';
import { getLicenseService } from '@core/licenseservice/service.ts';
import type { TextModalKey } from '@core/licenseservice/types.ts';

const createLicenseModalBinder = (key: TextModalKey): ((modal: HTMLElement) => ModalBinder) => {
    return (modal: HTMLElement): ModalBinder => {
        const resources = new ResourceTracker();
        const config = TEXT_MODAL_CONFIGS[key];
        if (modal.id !== config.id) {
            throw new Error(`License modal root id mismatch (expected "${config.id}", found "${modal.id}")`);
        }
        const { copyButton } = resolveTextModalButtons(config.id, modal);
        if (!copyButton) {
            throw new Error(`License modal copy button is missing for "${config.id}"`);
        }
        copyButton.setAttribute('type', 'button');
        resources.addEventListener(copyButton, 'click', (event: Event) => {
            event.preventDefault();
            event.stopPropagation();
            terminateHandledPromise(getLicenseService().handleCopy(key));
        });
        return { dispose: () => resources.cleanup() };
    };
};

const createLicenseModalDefinition = (key: TextModalKey): ModalDefinition => {
    const config = TEXT_MODAL_CONFIGS[key];
    return {
        id: config.id,
        layout: 'md',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => createTextModalElement(config),
        bind: createLicenseModalBinder(key)
    };
};

const LICENSE_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze(TEXT_MODAL_KEYS.map((key) => createLicenseModalDefinition(key)));

export { LICENSE_MODAL_DEFINITIONS };
