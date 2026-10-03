/* SoAI - SoAIBench GPU selection and intro composer within the run modal [frontend/assets/ts/features/hardware/modals/soaibenchrun/selection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton } from '@core/modals/footerButtons.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, joinUiHtml, uiAttr, uiAttributes, uiHtml } from '@core/security/uiHtml.ts';
import { HARDWARE_SOAIBENCH_RUN_DISMISS_ACTION, HARDWARE_SOAIBENCH_RUN_HISTORY_ACTION, HARDWARE_SOAIBENCH_RUN_PICK_ACTION, HARDWARE_SOAIBENCH_RUN_START_ACTION } from '@features/hardware/modals/soaibenchrun/constants.ts';
import type { SoAIBenchComposer, SoAIBenchRunOpenRequest } from '@features/hardware/modals/soaibenchrun/types.ts';
import { renderGpuLabel, renderRunIntro } from '@features/hardware/modals/soaibenchrun/view.ts';

interface SoAIBenchComposerContext {
    modalId: string;
    hasSections: boolean;
    isBusy(deviceId: string): boolean;
    hasHistory(deviceId: string): boolean;
}

const CLOSED_COMPOSER: SoAIBenchComposer = { type: 'closed' };

const renderDismissButton = (label: string): TrustedHtml => renderModalFooterActionButton({ text: label, action: HARDWARE_SOAIBENCH_RUN_DISMISS_ACTION, variant: 'neutral', className: 'hardware-soaibench-composer-dismiss' });

const renderPickerOption = (option: SoAIBenchRunOpenRequest, position: number, context: SoAIBenchComposerContext): TrustedHtml => {
    const label = renderGpuLabel(option);
    if (!context.isBusy(option.deviceId)) {
        return uiHtml`<button type="button" class="ui-button ui-variant-neutral hardware-soaibench-gpu-option" data-action="${uiAttr(HARDWARE_SOAIBENCH_RUN_PICK_ACTION)}" data-selection-index="${uiAttr(position)}"${renderLabelAttributes(label)}>${label}</button>`;
    }
    const reasonId = modalUiId(context.modalId, `busy-${String(position)}`);
    return uiHtml`<button type="button" class="ui-button ui-variant-neutral hardware-soaibench-gpu-option" data-action="${uiAttr(HARDWARE_SOAIBENCH_RUN_PICK_ACTION)}" data-selection-index="${uiAttr(position)}" aria-describedby="${uiAttr(reasonId)}"${renderLabelAttributes({ ariaLabel: label, tooltip: i18n.t('hardware.modals.soaibenchRun.gpuBusy') })}${uiAttributes({ disabled: true, 'aria-disabled': 'true', tabindex: '-1' })}><span>${label}</span><span class="hardware-soaibench-gpu-option-reason" id="${uiAttr(reasonId)}">${i18n.t('hardware.modals.soaibenchRun.gpuBusy')}</span></button>`;
};

const renderPicker = (options: readonly SoAIBenchRunOpenRequest[], context: SoAIBenchComposerContext): TrustedHtml => {
    const list = options.length > 0 ? uiHtml`<div class="hardware-soaibench-gpu-list">${joinUiHtml(options.map((option, position) => renderPickerOption(option, position, context)))}</div>` : uiHtml`<p class="hardware-soaibench-gpu-empty">${i18n.t('hardware.modals.soaibenchRun.noGpus')}</p>`;
    const dismiss = context.hasSections ? uiHtml`<div class="hardware-soaibench-run-actions">${renderDismissButton(i18n.t('common.cancel'))}</div>` : EMPTY_UI_HTML;
    return uiHtml`<h3 class="hardware-soaibench-gpu-selection-title">${i18n.t('hardware.modals.soaibenchRun.selectGpu')}</h3>${list}${dismiss}`;
};

const renderIntro = (request: SoAIBenchRunOpenRequest, fromPicker: boolean, context: SoAIBenchComposerContext): TrustedHtml => {
    const dismiss = fromPicker ? renderDismissButton(i18n.t('common.back')) : context.hasSections ? renderDismissButton(i18n.t('common.cancel')) : EMPTY_UI_HTML;
    const history = context.hasHistory(request.deviceId) ? renderModalFooterActionButton({ text: i18n.t('hardware.modals.soaibenchRun.history'), ariaLabel: i18n.t('hardware.modals.soaibenchRun.ariaLabels.history'), action: HARDWARE_SOAIBENCH_RUN_HISTORY_ACTION, variant: 'neutral' }) : EMPTY_UI_HTML;
    const start = renderModalFooterActionButton({ text: i18n.t('hardware.modals.soaibenchRun.start'), ariaLabel: i18n.t('hardware.modals.soaibenchRun.ariaLabels.start'), id: modalUiId(context.modalId, 'start'), action: HARDWARE_SOAIBENCH_RUN_START_ACTION, variant: 'accent' });
    return uiHtml`${renderRunIntro(request)}<div class="hardware-soaibench-run-actions">${dismiss}${history}${start}</div>`;
};

class SoAIBenchGpuSelection {
    #composer: SoAIBenchComposer = CLOSED_COMPOSER;
    #pickerOptions: readonly SoAIBenchRunOpenRequest[] = [];

    get composer(): SoAIBenchComposer {
        return this.#composer;
    }

    showPicker(options: readonly SoAIBenchRunOpenRequest[]): void {
        this.#pickerOptions = [...options];
        this.#composer = { type: 'picker' };
    }

    showIntro(request: SoAIBenchRunOpenRequest): void {
        this.#composer = { type: 'intro', request, fromPicker: false };
    }

    select(positionText: string): SoAIBenchRunOpenRequest {
        const position = Number(positionText);
        const request = this.#composer.type === 'picker' && Number.isSafeInteger(position) && position >= 0 ? this.#pickerOptions[position] : undefined;
        if (request === undefined) {
            throw new Error('SoAIBench GPU selection is no longer available');
        }
        this.#composer = { type: 'intro', request, fromPicker: true };
        return request;
    }

    dismiss(): void {
        this.#composer = this.#composer.type === 'intro' && this.#composer.fromPicker ? { type: 'picker' } : CLOSED_COMPOSER;
    }

    close(): void {
        this.#composer = CLOSED_COMPOSER;
        this.#pickerOptions = [];
    }

    requireIntroRequest(): SoAIBenchRunOpenRequest {
        if (this.#composer.type !== 'intro') {
            throw new Error('SoAIBench start requires a selected GPU');
        }
        return this.#composer.request;
    }

    render(context: SoAIBenchComposerContext): TrustedHtml {
        if (this.#composer.type === 'picker') {
            return renderPicker(this.#pickerOptions, context);
        }
        if (this.#composer.type === 'intro') {
            return renderIntro(this.#composer.request, this.#composer.fromPicker, context);
        }
        return EMPTY_UI_HTML;
    }
}

export { SoAIBenchGpuSelection };
export type { SoAIBenchComposerContext };
