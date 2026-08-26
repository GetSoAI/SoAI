/* SoAI - Chat feature controls [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/controls.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';

type ToggleLabels = {
    trueLabel: string;
    falseLabel: string;
};

const resolveEnabledDisabledToggleLabels = (): ToggleLabels => ({
    trueLabel: i18n.t('chat.parameters.enabled'),
    falseLabel: i18n.t('chat.parameters.disabled')
});

const resolveSystemPromptLockToggleLabels = (): ToggleLabels => ({
    trueLabel: i18n.t('chat.configuration.systemPromptLockLocked'),
    falseLabel: i18n.t('chat.configuration.systemPromptLockUnlocked')
});

const buildToggleSwitchMarkup = (inputArguments: { modalId: string; token: string; checked: boolean; labels: ToggleLabels; inputClassName: string; inline?: boolean | undefined; disabled?: boolean | undefined; dataParameter?: string | undefined; dataSetting?: string | undefined }): string => {
    const dataset: Record<string, string> = {};
    if (inputArguments.dataParameter) {
        dataset['param'] = inputArguments.dataParameter;
    }
    if (inputArguments.dataSetting) {
        dataset['setting'] = inputArguments.dataSetting;
    }
    return renderToggleSwitch({
        id: modalUiId(inputArguments.modalId, inputArguments.token),
        checked: inputArguments.checked,
        labels: inputArguments.labels,
        inline: inputArguments.inline,
        disabled: inputArguments.disabled,
        inputClassName: inputArguments.inputClassName,
        inputDataset: Object.keys(dataset).length ? dataset : undefined,
        wrapperTag: 'div'
    });
};

export { buildToggleSwitchMarkup, resolveEnabledDisabledToggleLabels, resolveSystemPromptLockToggleLabels };
