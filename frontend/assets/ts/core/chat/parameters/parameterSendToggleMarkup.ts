/* SoAI - Chat parameter send toggle markup [frontend/assets/ts/core/chat/parameters/parameterSendToggleMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';

import type { ChatParameterControlsStrings } from '@core/chat/parameters/parameterControlStrings.ts';

type ParameterSendToggleStrings = Pick<ChatParameterControlsStrings, 'enabledLabel' | 'disabledLabel' | 'sendParameterToggle'>;

const renderParameterSendToggleMarkup = (inputArguments: { modalId: string; token: string; flag: string; checked: boolean; strings: ParameterSendToggleStrings }): string => {
    return renderToggleSwitch({
        id: modalUiId(inputArguments.modalId, inputArguments.token),
        checked: inputArguments.checked,
        labels: {
            trueLabel: inputArguments.strings.enabledLabel,
            falseLabel: inputArguments.strings.disabledLabel
        },
        inputClassName: 'chat-config-field-toggle-input',
        inputDataset: {
            'param': inputArguments.flag
        },
        ariaLabel: inputArguments.strings.sendParameterToggle,
        title: inputArguments.strings.sendParameterToggle,
        wrapperClassName: 'chat-config-field-toggle',
        wrapperDataset: {
            tooltip: inputArguments.strings.sendParameterToggle
        },
        wrapperTag: 'div',
        showLabel: true
    });
};

const renderParameterFieldHeader = (inputArguments: { modalId: string; labelFor: string; label: string; token: string; flag: string; checked: boolean; strings: ParameterSendToggleStrings }): string => {
    return `<div class="chat-config-field-header"><label for="${uiAttr(modalUiId(inputArguments.modalId, inputArguments.labelFor)).html}">${inputArguments.label}</label>${renderParameterSendToggleMarkup(inputArguments)}</div>`;
};

export { renderParameterFieldHeader, renderParameterSendToggleMarkup };
export type { ParameterSendToggleStrings };
