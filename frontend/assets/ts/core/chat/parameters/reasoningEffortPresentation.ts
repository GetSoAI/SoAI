/* SoAI - Reasoning effort selector presentation and validation [frontend/assets/ts/core/chat/parameters/reasoningEffortPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameterControlsStrings } from '@core/chat/parameters/parameterControlStrings.ts';
import { REASONING_EFFORT_LEVELS, ReasoningEffortLevel, isReasoningEffortLevel, isReasoningEffortSupported } from '@core/chat/parameters/reasoningEffort.ts';
import { dom } from '@core/dom/dom.ts';
import { setControlValidity } from '@core/dom/formValidity.ts';
import { replaceSelectOptions, type SelectOptionDefinition } from '@core/dom/selectOptions.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';

const resolveReasoningEffortLabel = (level: ReasoningEffortLevel, strings: ChatParameterControlsStrings): string => {
    if (level === ReasoningEffortLevel.None) return strings.reasoningEffortNone;
    if (level === ReasoningEffortLevel.Minimal) return strings.reasoningEffortMinimal;
    if (level === ReasoningEffortLevel.Low) return strings.reasoningEffortLow;
    if (level === ReasoningEffortLevel.Medium) return strings.reasoningEffortMedium;
    if (level === ReasoningEffortLevel.High) return strings.reasoningEffortHigh;
    if (level === ReasoningEffortLevel.ExtraHigh) return strings.reasoningEffortXHigh;
    if (level === ReasoningEffortLevel.Maximum) return strings.reasoningEffortMaximum;
    throw new Error(`Unsupported reasoning effort level: ${String(level)}`);
};

const buildReasoningEffortOptions = (levels: readonly ReasoningEffortLevel[], strings: ChatParameterControlsStrings): SelectOptionDefinition[] => [{ value: '', label: strings.disabledLabel }, ...levels.map((level) => ({ value: level, label: resolveReasoningEffortLabel(level, strings) }))];

const renderReasoningEffortOptionsMarkup = (strings: ChatParameterControlsStrings): string =>
    buildReasoningEffortOptions(REASONING_EFFORT_LEVELS, strings)
        .map((option) => `<option value="${uiAttr(option.value).html}">${uiText(option.label).html}</option>`)
        .join('');

class ReasoningEffortControl {
    readonly #select: HTMLSelectElement;
    readonly #status: HTMLElement;
    readonly #supportedLevels: readonly ReasoningEffortLevel[] | null;
    readonly #unsupportedMessage: string;

    constructor(modal: HTMLElement, modalId: string, currentValue: string | null, supportedLevels: readonly ReasoningEffortLevel[] | null, strings: ChatParameterControlsStrings) {
        const select = dom.resolve(modalUiSelector(modalId, 'reasoning-effort-select'), modal);
        const status = dom.resolve(modalUiSelector(modalId, 'reasoning-effort-support-error'), modal);
        if (!(select instanceof HTMLSelectElement)) throw new Error('Reasoning effort selector is missing');
        if (!(status instanceof HTMLElement)) throw new Error('Reasoning effort validation status is missing');
        this.#select = select;
        this.#status = status;
        this.#supportedLevels = supportedLevels === null ? null : Object.freeze([...supportedLevels]);
        this.#unsupportedMessage = strings.reasoningEffortUnsupportedMessage;
        const visibleLevels = this.#supportedLevels ?? REASONING_EFFORT_LEVELS;
        const options = buildReasoningEffortOptions(visibleLevels, strings);
        if (currentValue && !isReasoningEffortSupported(currentValue, this.#supportedLevels)) {
            const label = isReasoningEffortLevel(currentValue) ? resolveReasoningEffortLabel(currentValue, strings) : currentValue;
            options.push({ value: currentValue, label: `${label} (${strings.reasoningEffortUnsupportedSuffix})`, disabled: true });
        }
        replaceSelectOptions(select, options);
        setSelectValueAndSyncDefault(select, currentValue ?? '');
    }

    syncValidity(value: string | null): boolean {
        const valid = isReasoningEffortSupported(value, this.#supportedLevels);
        this.#select.setCustomValidity(valid ? '' : this.#unsupportedMessage);
        setControlValidity(this.#select, valid, '.setting-change-surface');
        this.#status.textContent = valid ? '' : this.#unsupportedMessage;
        this.#status.hidden = valid;
        return valid;
    }
}

export { ReasoningEffortControl, renderReasoningEffortOptionsMarkup };
