/* SoAI - SoAI Bench run modal DOM contracts [frontend/assets/ts/features/hardware/modals/soaibenchrun/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { HARDWARE_SOAIBENCH_RUN_MODAL_ID } from '@features/hardware/modals/constants.ts';
import { HARDWARE_SOAIBENCH_RUN_START_ACTION } from '@features/hardware/modals/soaibenchrun/constants.ts';
import type { SoAIBenchRunModalHost } from '@features/hardware/modals/soaibenchrun/types.ts';

const SELECTORS = {
    body: '.modal-body',
    toolbar: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'toolbar'),
    composer: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'composer'),
    runs: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'runs'),
    composerFocus: `.hardware-soaibench-gpu-option:not([disabled]), [data-action="${HARDWARE_SOAIBENCH_RUN_START_ACTION}"]`
};

const requireModalBody = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLElement => host.requireHTMLElement(SELECTORS.body, modalRoot);

const requireToolbar = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLElement => host.requireHTMLElement(SELECTORS.toolbar, modalRoot);

const requireComposerElement = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLElement => host.requireHTMLElement(SELECTORS.composer, modalRoot);

const requireRunList = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLElement => host.requireHTMLElement(SELECTORS.runs, modalRoot);

const resolveComposerFocusTarget = (composer: HTMLElement): HTMLElement | null => {
    const target = dom.resolve(SELECTORS.composerFocus, composer);
    return target instanceof HTMLElement ? target : null;
};

export { requireComposerElement, requireModalBody, requireRunList, requireToolbar, resolveComposerFocusTarget };
