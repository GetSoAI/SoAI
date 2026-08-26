/* SoAI - Models feature markup [frontend/assets/ts/features/models/modals/virtualmodelsmodal/constituentpicker/markup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { getIconSync } from '@core/ui/icons/iconservice/public.ts';

interface ConstituentPickerMarkupOptions {
    modalId: string;
    token: string;
    getIconSync: typeof getIconSync;
}

const buildConstituentPickerMarkup = ({ modalId, token, getIconSync: getIcon }: ConstituentPickerMarkupOptions): TrustedHtml => {
    const searchInputId = modalUiId(modalId, `${token}-search`);
    const searchButtonId = modalUiId(modalId, `${token}-search-button`);
    const resultsId = modalUiId(modalId, `${token}-results`);
    const storeId = modalUiId(modalId, token);
    const placeholder = uiAttr(i18n.t('models.modal.virtualModels.searchPlaceholder'));
    const searchLabel = uiAttr(i18n.t('models.modal.virtualModels.searchButton'));
    return uiHtml`
        <div class="constituent-picker" data-constituent-picker>
            <div class="form-row-split form-row-split--search">
                <div class="form-col-main">
                    <div class="searchbar-container searchbar-container--collection">
                        <input type="text" id="${searchInputId}" class="form-input searchbar-input" placeholder="${placeholder}" autocomplete="off">
                        <span class="searchbar-icon">${getIcon('search', { size: 16, strokeWidth: 1.5 })}</span>
                    </div>
                </div>
                <div class="form-col-secondary form-col-action">
                    <button class="ui-button" id="${searchButtonId}" type="button" aria-label="${searchLabel}" data-tooltip="${searchLabel}">${i18n.t('models.modal.virtualModels.searchButton')}</button>
                </div>
            </div>
            <div class="form-help">${i18n.t('models.modal.virtualModels.selectModels')}</div>
            <div class="constituent-results" id="${resultsId}"></div>
            <select id="${storeId}" class="constituent-store" multiple hidden></select>
        </div>
    `;
};

export { buildConstituentPickerMarkup };
