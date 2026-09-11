/* SoAI - Shared file explorer browser folder picker modal DOM [frontend/assets/ts/core/fileexplorerbrowser/folderPickerModalDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';

const FOLDER_PICKER_MODAL_ID = 'folder-picker-modal';

type FolderPickerModalElements = {
    titleElement: HTMLElement;
    bodySlot: HTMLElement;
    footerLeftSlot: HTMLElement;
    footerRightSlot: HTMLElement;
    currentPathElement: HTMLInputElement;
    rootSelect: HTMLSelectElement | null;
    statusElement: HTMLElement;
    tableElement: HTMLTableElement;
    rowsElement: HTMLElement;
    sortHeaderElement: HTMLElement;
    searchInput: HTMLInputElement;
    manualInput: HTMLInputElement;
    confirmButton: HTMLButtonElement;
    cancelButton: HTMLButtonElement;
    resetButton: HTMLButtonElement | null;
};

type FolderPickerModalScaffoldElements = Readonly<{
    titleElement: HTMLElement;
    bodySlot: HTMLElement;
    footerLeftSlot: HTMLElement;
    footerRightSlot: HTMLElement;
}>;

const folderPickerModalDefinition: ModalDefinition = {
    id: FOLDER_PICKER_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(FOLDER_PICKER_MODAL_ID, 'search'),
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = FOLDER_PICKER_MODAL_ID;
        const header = renderStandardModalHeader({ modalId, title: '', description: i18n.t('common.modalDescriptions.folderPicker'), titleId: modalUiId(modalId, 'title'), closeLabel: i18n.t('common.close') });
        const body = renderModalBody(uiHtml`<div id="${uiAttr(modalUiId(modalId, 'body-slot'))}"></div>`);
        const footer = renderSplitModalFooter({
            left: uiHtml`<div id="${uiAttr(modalUiId(modalId, 'footer-left-slot'))}"></div>`,
            right: uiHtml`<div id="${uiAttr(modalUiId(modalId, 'footer-right-slot'))}"></div>`
        });
        return createModalElement({
            id: modalId,
            contentClassName: modalId,
            header,
            body,
            footer
        });
    }
};

const resolveFolderPickerModalScaffoldElements = (modal: HTMLElement): FolderPickerModalScaffoldElements => {
    const modalId = FOLDER_PICKER_MODAL_ID;
    const titleElement = dom.resolve(modalUiSelector(modalId, 'title'), modal);
    const bodySlot = dom.resolve(modalUiSelector(modalId, 'body-slot'), modal);
    const footerLeftSlot = dom.resolve(modalUiSelector(modalId, 'footer-left-slot'), modal);
    const footerRightSlot = dom.resolve(modalUiSelector(modalId, 'footer-right-slot'), modal);

    if (!(titleElement instanceof HTMLElement) || !(bodySlot instanceof HTMLElement) || !(footerLeftSlot instanceof HTMLElement) || !(footerRightSlot instanceof HTMLElement)) {
        throw new Error('Folder picker modal failed to initialize required scaffold elements');
    }

    return Object.freeze({ titleElement, bodySlot, footerLeftSlot, footerRightSlot });
};

const resolveFolderPickerModalElements = (modal: HTMLElement, requireResetButton: boolean, requireRootSelect: boolean): FolderPickerModalElements => {
    const modalId = FOLDER_PICKER_MODAL_ID;
    const { titleElement, bodySlot, footerLeftSlot, footerRightSlot } = resolveFolderPickerModalScaffoldElements(modal);
    const currentPathElement = dom.resolve(modalUiSelector(modalId, 'current'), modal);
    const rootSelectCandidate = dom.resolve(modalUiSelector(modalId, 'root'), modal);
    const rootSelect = rootSelectCandidate instanceof HTMLSelectElement ? rootSelectCandidate : null;
    const statusElement = dom.resolve(modalUiSelector(modalId, 'status'), modal);
    const tableElement = dom.resolve(modalUiSelector(modalId, 'table'), modal);
    const rowsElement = dom.resolve(modalUiSelector(modalId, 'rows'), modal);
    const sortHeaderElement = dom.resolve(modalUiSelector(modalId, 'sort-name'), modal);
    const searchInput = dom.resolve(modalUiSelector(modalId, 'search'), modal);
    const manualInput = dom.resolve(modalUiSelector(modalId, 'manual'), modal);
    const confirmButton = dom.resolve(modalUiSelector(modalId, 'confirm'), modal);
    const cancelButton = dom.resolve(modalUiSelector(modalId, 'cancel'), modal);
    const resetButtonCandidate = dom.resolve(modalUiSelector(modalId, 'reset'), modal);
    const resetButton = resetButtonCandidate instanceof HTMLButtonElement ? resetButtonCandidate : null;

    if (!(titleElement instanceof HTMLElement) || !(bodySlot instanceof HTMLElement) || !(footerLeftSlot instanceof HTMLElement) || !(footerRightSlot instanceof HTMLElement) || !(currentPathElement instanceof HTMLInputElement) || !(statusElement instanceof HTMLElement) || !(tableElement instanceof HTMLTableElement) || !(rowsElement instanceof HTMLElement) || !(sortHeaderElement instanceof HTMLElement) || !(searchInput instanceof HTMLInputElement) || !(manualInput instanceof HTMLInputElement) || !(confirmButton instanceof HTMLButtonElement) || !(cancelButton instanceof HTMLButtonElement) || (requireResetButton && !resetButton) || (requireRootSelect && !rootSelect)) {
        throw new Error('Folder picker modal failed to initialize required elements');
    }

    return {
        titleElement,
        bodySlot,
        footerLeftSlot,
        footerRightSlot,
        currentPathElement,
        rootSelect,
        statusElement,
        tableElement,
        rowsElement,
        sortHeaderElement,
        searchInput,
        manualInput,
        confirmButton,
        cancelButton,
        resetButton
    };
};

export { FOLDER_PICKER_MODAL_ID, folderPickerModalDefinition, resolveFolderPickerModalElements, resolveFolderPickerModalScaffoldElements };
export type { FolderPickerModalElements, FolderPickerModalScaffoldElements };
