/* SoAI - SoAI Bench run modal DOM contracts [frontend/assets/ts/features/hardware/modals/soaibenchrun/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireButtonElement } from '@core/dom/typedElements.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { HARDWARE_SOAIBENCH_RUN_MODAL_ID } from '@features/hardware/modals/constants.ts';
import type { SoAIBenchRunModalHost } from '@features/hardware/modals/soaibenchrun/types.ts';

const SELECTORS = {
    body: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'body'),
    copy: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'copy'),
    download: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'download'),
    history: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'history'),
    start: modalUiSelector(HARDWARE_SOAIBENCH_RUN_MODAL_ID, 'start')
};

const requireRunBody = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLElement => {
    return host.requireHTMLElement(SELECTORS.body, modalRoot);
};

const requireStartButton = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButtonElement(host, SELECTORS.start, 'SoAIBench run start button', modalRoot);
};

const requireHistoryButton = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButtonElement(host, SELECTORS.history, 'SoAIBench run history button', modalRoot);
};

const requireCopyButton = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButtonElement(host, SELECTORS.copy, 'SoAIBench run copy button', modalRoot);
};

const requireDownloadButton = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement): HTMLButtonElement => {
    return requireButtonElement(host, SELECTORS.download, 'SoAIBench run download button', modalRoot);
};

type SoAIBenchRunFooterActionMode = 'start' | 'stop' | 'stopping';

const setStartButtonState = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement, options: { hidden: boolean; disabled: boolean; mode: SoAIBenchRunFooterActionMode; label: string; ariaLabel: string }): void => {
    const button = requireStartButton(host, modalRoot);
    button.hidden = options.hidden;
    button.disabled = options.disabled;
    button.textContent = options.label;
    button.setAttribute('aria-label', options.ariaLabel);
    setTooltipText(button, options.ariaLabel);
    button.setAttribute('aria-disabled', options.disabled ? 'true' : 'false');
    button.classList.remove('ui-variant-accent', 'ui-variant-danger');
    button.classList.add(options.mode === 'start' ? 'ui-variant-accent' : 'ui-variant-danger');
};

const setHistoryButtonState = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement, options: { visible: boolean; disabled: boolean }): void => {
    const button = requireHistoryButton(host, modalRoot);
    button.hidden = !options.visible;
    if (options.visible) {
        button.removeAttribute('aria-hidden');
    } else {
        button.setAttribute('aria-hidden', 'true');
    }
    const disabled = !options.visible || options.disabled;
    button.disabled = disabled;
    button.setAttribute('aria-disabled', disabled ? 'true' : 'false');
};

const setExportButtonState = (host: SoAIBenchRunModalHost, modalRoot: HTMLElement, visible: boolean): void => {
    for (const button of [requireCopyButton(host, modalRoot), requireDownloadButton(host, modalRoot)]) {
        button.hidden = !visible;
        button.disabled = !visible;
        button.setAttribute('aria-disabled', visible ? 'false' : 'true');
    }
};

export { requireRunBody, setExportButtonState, setHistoryButtonState, setStartButtonState };
export type { SoAIBenchRunFooterActionMode };
