/* SoAI - Automation feature color picker markup [frontend/assets/ts/features/automation/modals/markup/colorPickerMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr, uiText } from '@core/security/uiHtml.ts';

const renderAutomationColorPickerMarkup = (modalId: string): string => {
    const radioName = modalUiId(modalId, 'color');
    return [
        { value: '', className: 'automation-color-option-none', label: i18n.t('chat.colors.none') },
        { value: 'Red', className: 'automation-color-option-red', label: i18n.t('chat.colors.red') },
        { value: 'Yellow', className: 'automation-color-option-yellow', label: i18n.t('chat.colors.yellow') },
        { value: 'Purple', className: 'automation-color-option-purple', label: i18n.t('chat.colors.purple') },
        { value: 'Green', className: 'automation-color-option-green', label: i18n.t('chat.colors.green') },
        { value: 'Blue', className: 'automation-color-option-blue', label: i18n.t('chat.colors.blue') }
    ]
        .map((option) => {
            const checkedAttr = option.value === '' ? ' checked' : '';
            return `<label class="automation-color-option ${option.className}" data-tooltip="${uiAttr(option.label).html}" aria-label="${uiAttr(option.label).html}">` + `<input class="automation-color-input visually-hidden" type="radio" name="${radioName}" value="${uiAttr(option.value).html}"${checkedAttr}>` + `<span class="automation-color-swatch" aria-hidden="true"></span>` + `<span class="visually-hidden">${uiText(option.label).html}</span>` + `</label>`;
        })
        .join('');
};

export { renderAutomationColorPickerMarkup };
