/* SoAI - Frontend chat character map modal definition [frontend/assets/ts/features/chat/charactermap/definition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { renderModalBody, renderModalLoadingState, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';
import { CHARACTER_MAP_ACTIONS } from '@features/chat/charactermap/actions.ts';
import { CHARACTER_MAP_DEFAULT_FONT_ID, CHARACTER_MAP_FONTS, type CharacterMapFontId } from '@features/chat/charactermap/fontCatalog.ts';
import { CHAT_CHARACTER_MAP_MODAL_ID } from '@features/chat/modals/constants.ts';

const renderFontLabel = (fontId: CharacterMapFontId): string => {
    if (fontId === 'soai-sans') return i18n.t('chat.characterMap.fonts.soaiSans');
    if (fontId === 'soai-mono') return i18n.t('chat.characterMap.fonts.soaiMono');
    if (fontId === 'serif') return i18n.t('chat.characterMap.fonts.serif');
    if (fontId === 'sans-serif') return i18n.t('chat.characterMap.fonts.sansSerif');
    if (fontId === 'monospace') return i18n.t('chat.characterMap.fonts.monospace');
    if (fontId === 'symbols') return i18n.t('chat.characterMap.fonts.symbols');
    return i18n.t('chat.characterMap.fonts.emoji');
};

const renderFontOptions = (): TrustedHtml => {
    const options = CHARACTER_MAP_FONTS.map((font) => (font.id === CHARACTER_MAP_DEFAULT_FONT_ID ? uiHtml`<option value="${uiAttr(font.id)}" selected>${uiText(renderFontLabel(font.id))}</option>` : uiHtml`<option value="${uiAttr(font.id)}">${uiText(renderFontLabel(font.id))}</option>`));
    return toTrustedUiHtml(options.map((option) => option.html).join(''));
};

const renderSelectControl = (id: string, className: string, options: TrustedHtml): TrustedHtml => {
    const select = uiHtml`<select id="${uiAttr(id)}" class="${uiAttr(className)}" disabled aria-disabled="true">${options}</select>`;
    return toTrustedUiHtml(renderStandardDropdownSelectControl(select.html));
};

const renderSearch = (modalId: string): TrustedHtml => {
    const searchId = modalUiId(modalId, 'search');
    const label = i18n.t('chat.characterMap.search');
    return uiHtml`
        <div class="form-group chat-character-map-search">
            <label for="${uiAttr(searchId)}">${uiText(label)}</label>
            <div class="form-row-split form-row-split--search ui-collection-search-row">
                <div class="form-col-main ui-collection-search-row__field">
                    <div class="searchbar-container searchbar-container--collection">
                        <input type="text" id="${uiAttr(searchId)}" class="form-input searchbar-input" placeholder="${uiAttr(i18n.t('chat.characterMap.searchPlaceholder'))}" autocomplete="off" spellcheck="false">
                        ${renderSearchFieldActions()}
                    </div>
                </div>
                <div class="form-col-secondary form-col-action ui-collection-search-row__action">
                    <button type="button" class="ui-button" data-action="${uiAttr(CHARACTER_MAP_ACTIONS.SEARCH)}" ${renderLabelAttributes(label)} disabled>${uiText(label)}</button>
                </div>
            </div>
        </div>
    `;
};

const renderControls = (modalId: string): TrustedHtml => {
    const fontId = modalUiId(modalId, 'font');
    const subsetId = modalUiId(modalId, 'subset');
    return uiHtml`
        <section class="chat-character-map-controls">
            <div class="form-group chat-character-map-select-field">
                <label for="${uiAttr(fontId)}">${uiText(i18n.t('chat.characterMap.font'))}</label>
                ${renderSelectControl(fontId, 'form-input chat-character-map-font-select', renderFontOptions())}
            </div>
            <div class="form-group chat-character-map-select-field">
                <label for="${uiAttr(subsetId)}">${uiText(i18n.t('chat.characterMap.subset'))}</label>
                ${renderSelectControl(subsetId, 'form-input chat-character-map-subset-select', EMPTY_UI_HTML)}
            </div>
            ${renderSearch(modalId)}
            <p class="form-help chat-character-map-font-hint">${uiText(i18n.t('chat.characterMap.fontHint'))}</p>
        </section>
    `;
};

const renderWorkbench = (modalId: string): TrustedHtml => {
    const retryLabel = i18n.t('chat.characterMap.retry');
    return uiHtml`
        <div class="chat-character-map-workbench" data-character-map-workbench>
            ${renderControls(modalId)}
            <div id="${uiAttr(modalUiId(modalId, 'status'))}" class="chat-character-map-status" aria-live="polite"></div>
            <div class="chat-character-map-results-surface">
                ${renderModalLoadingState({ id: modalUiId(modalId, 'loading'), text: i18n.t('common.loading') })}
                <div id="${uiAttr(modalUiId(modalId, 'error'))}" class="chat-character-map-error u-hidden">
                    <p>${uiText(i18n.t('chat.characterMap.loadFailure'))}</p>
                    <button type="button" class="ui-button ui-variant-neutral" data-action="${uiAttr(CHARACTER_MAP_ACTIONS.RETRY)}" ${renderLabelAttributes(retryLabel)}>${uiText(retryLabel)}</button>
                </div>
                <div id="${uiAttr(modalUiId(modalId, 'empty'))}" class="chat-character-map-empty u-hidden">${renderEmptyState({ title: i18n.t('chat.characterMap.noResults') })}</div>
                <div id="${uiAttr(modalUiId(modalId, 'grid'))}" class="chat-character-map-grid u-hidden" role="region" aria-label="${uiAttr(i18n.t('chat.characterMap.title'))}" aria-busy="false"></div>
            </div>
            <div class="chat-character-map-details surface-card card--flat">
                <div class="chat-character-map-details__metadata">
                    <div id="${uiAttr(modalUiId(modalId, 'code-points'))}" class="chat-character-map-code-points"></div>
                    <div id="${uiAttr(modalUiId(modalId, 'name'))}" class="chat-character-map-name"></div>
                </div>
                <button type="button" id="${uiAttr(modalUiId(modalId, 'select'))}" class="ui-button ui-variant-neutral" data-action="${uiAttr(CHARACTER_MAP_ACTIONS.SELECT)}" ${renderLabelAttributes(i18n.t('chat.characterMap.select'))} disabled>${uiText(i18n.t('chat.characterMap.select'))}</button>
            </div>
            <div class="form-group chat-character-map-staging">
                <label for="${uiAttr(modalUiId(modalId, 'staging'))}">${uiText(i18n.t('chat.characterMap.staging'))}</label>
                <input type="text" id="${uiAttr(modalUiId(modalId, 'staging'))}" class="form-input" autocomplete="off" autocapitalize="off" spellcheck="false">
            </div>
        </div>
    `;
};

const CHARACTER_MAP_MODAL_DEFINITION: ModalDefinition = Object.freeze({
    id: CHAT_CHARACTER_MAP_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(CHAT_CHARACTER_MAP_MODAL_ID, 'search'),
    createElement: (): HTMLElement => {
        const modalId = CHAT_CHARACTER_MAP_MODAL_ID;
        const closeLabel = i18n.t('common.close');
        const header = renderStandardModalHeader({ modalId, title: i18n.t('chat.characterMap.title'), description: i18n.t('chat.characterMap.description'), closeLabel });
        const body = renderModalBody(renderWorkbench(modalId), { className: 'modal-body--sectioned chat-character-map-modal-body' });
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
            right: uiHtml`${renderModalFooterActionButton({ id: modalUiId(modalId, 'copy'), action: CHARACTER_MAP_ACTIONS.COPY, text: i18n.t('common.copy'), variant: 'primary', disabled: true })}${renderModalFooterActionButton({ id: modalUiId(modalId, 'insert'), action: CHARACTER_MAP_ACTIONS.INSERT, text: i18n.t('chat.characterMap.insert'), variant: 'success', disabled: true })}`
        });
        return createModalElement({ id: modalId, rootAttributes: { 'data-page-scope': 'chat' }, header, body, footer });
    }
});

export { CHARACTER_MAP_MODAL_DEFINITION };
