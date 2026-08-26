/* SoAI - File Explorer address bar row markup [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerAddressBarWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, joinUiHtml, staticUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { FILE_EXPLORER_ACTION_NAVIGATE_HOME, FILE_EXPLORER_ACTION_NAVIGATE_NEXT, FILE_EXPLORER_ACTION_NAVIGATE_PREVIOUS, FILE_EXPLORER_ACTION_NAVIGATE_UP, FILE_EXPLORER_ACTION_PATH_EDIT_SAVE, FILE_EXPLORER_ACTION_REFRESH } from '@features/fileexplorer/public.ts';
import { FILE_EXPLORER_SEARCH_CONTAINER_ID } from '@pages/fileexplorer/contracts/contracts.ts';

interface FileExplorerAddressBarDependencies {
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
}

interface FileExplorerNavigationButton {
    id: string;
    action: string;
    icon: IconName;
    label: string;
    disabled?: boolean;
}

const renderNavigationButton = (dependencies: FileExplorerAddressBarDependencies, button: FileExplorerNavigationButton): TrustedHtml => {
    const icon = dependencies.getIconSync(button.icon, { size: 18, strokeWidth: 1.5 });
    const disabledMarkup = button.disabled === true ? staticUiHtml` disabled` : EMPTY_UI_HTML;
    return uiHtml`<button type="button" id="${uiAttr(button.id)}" class="ui-icon-button file-explorer-address-bar__navigate" data-action="${uiAttr(button.action)}"${disabledMarkup}${renderLabelAttributes(button.label)}>${renderIconSlot(icon)}</button>`;
};

const renderNavigation = (dependencies: FileExplorerAddressBarDependencies): TrustedHtml =>
    joinUiHtml(
        [
            { id: 'file-explorer-navigate-previous', action: FILE_EXPLORER_ACTION_NAVIGATE_PREVIOUS, icon: 'chevron-left', label: i18n.t('fileExplorer.actions.previous'), disabled: true },
            { id: 'file-explorer-navigate-next', action: FILE_EXPLORER_ACTION_NAVIGATE_NEXT, icon: 'chevron-right', label: i18n.t('fileExplorer.actions.next'), disabled: true },
            { id: 'file-explorer-navigate-up', action: FILE_EXPLORER_ACTION_NAVIGATE_UP, icon: 'chevron-up', label: i18n.t('fileExplorer.actions.up'), disabled: true },
            { id: 'file-explorer-navigate-home', action: FILE_EXPLORER_ACTION_NAVIGATE_HOME, icon: 'home', label: i18n.t('fileExplorer.actions.home'), disabled: true }
        ].map((button: FileExplorerNavigationButton) => renderNavigationButton(dependencies, button))
    );

const renderAddressField = (dependencies: FileExplorerAddressBarDependencies): TrustedHtml => {
    const editLabel = i18n.t('fileExplorer.actions.editPath');
    const refreshLabel = i18n.t('fileExplorer.aria.refresh');
    const goLabel = i18n.t('fileExplorer.actions.go');
    const refreshIcon = dependencies.getIconSync('refresh', { size: 18, strokeWidth: 1.5 });
    const goIcon = dependencies.getIconSync('arrow-right', { size: 18, strokeWidth: 1.5 });
    return uiHtml`<div class="file-explorer-address-bar__field ui-inline-action-field"><div id="file-explorer-current-path" class="file-explorer-breadcrumb" tabindex="-1" role="navigation" aria-label="${uiAttr(i18n.t('fileExplorer.aria.breadcrumb'))}" data-current-path="/"></div><input type="text" id="file-explorer-current-path-input" class="ui-inline-text-edit__input file-explorer-address-bar__input u-hidden" aria-label="${uiAttr(editLabel)}"><button type="button" id="file-explorer-refresh" class="ui-inline-action-field__button file-explorer-address-bar__refresh" data-action="${uiAttr(FILE_EXPLORER_ACTION_REFRESH)}"${renderLabelAttributes(refreshLabel)}><span class="ui-inline-action-field__icon" aria-hidden="true">${refreshIcon}</span></button><button type="button" class="ui-inline-action-field__button ui-inline-text-edit__save file-explorer-address-bar__save u-hidden" data-action="${uiAttr(FILE_EXPLORER_ACTION_PATH_EDIT_SAVE)}"${renderLabelAttributes(goLabel)}><span class="ui-inline-action-field__icon" aria-hidden="true">${goIcon}</span></button></div>`;
};

const renderFileExplorerAddressBar = (dependencies: FileExplorerAddressBarDependencies): TrustedHtml => {
    return uiHtml`<div class="file-explorer-address-bar" role="toolbar" aria-label="${uiAttr(i18n.t('fileExplorer.aria.addressBar'))}">${renderNavigation(dependencies)}${renderAddressField(dependencies)}<div id="${uiAttr(FILE_EXPLORER_SEARCH_CONTAINER_ID)}" class="file-explorer-address-bar__search" role="search"></div></div>`;
};

export { renderFileExplorerAddressBar };
