/* SoAI - File explorer page rendering layer header widget [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerHeaderWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import type { GenerateStandardHeaderOptions, HeaderActionDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { resolveInitialViewMode } from '@core/uiprimitives/viewmode/public.ts';
import { renderSortControl } from '@core/uiprimitives/sortableList.ts';
import { FILE_EXPLORER_ACTION_NEW_ENTRY, FILE_EXPLORER_ACTION_TOGGLE_VIEW_MODE } from '@features/fileexplorer/public.ts';
import { FILE_EXPLORER_NEW_ENTRY_OPTION_VALUES, type FileExplorerNewEntryOptionValue } from '@pages/fileexplorer/contracts/contracts.ts';
import { createFileExplorerSortControlDefinition, type FileExplorerSortState } from '@pages/fileexplorer/controllers/page/fileExplorerPageControlsController.ts';
import { renderFileExplorerAddressBar } from '@pages/fileexplorer/rendering/FileExplorerAddressBarWidget.ts';
import { buildFileExplorerCommandActions } from '@pages/fileexplorer/rendering/FileExplorerCommandActionsWidget.ts';

type FileExplorerViewMode = 'list' | 'icons';

interface FileExplorerHeaderWidgetDependencies {
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
    generateStandardHeader: (options: GenerateStandardHeaderOptions) => TrustedHtml;
    sortState: FileExplorerSortState;
}

interface FileExplorerHeaderWidgetResult {
    header: TrustedHtml;
    initialViewMode: FileExplorerViewMode;
}

const VIEW_MODE_STORAGE_KEY = 'soai.fileExplorer.viewMode';

const resolveNewEntryLabel = (value: FileExplorerNewEntryOptionValue): string => {
    switch (value) {
        case '':
            return i18n.t('fileExplorer.actions.newEntryLabel');
        case 'folder':
            return i18n.t('fileExplorer.actions.createFolder');
        case 'file':
            return i18n.t('fileExplorer.actions.createFile');
        case 'uploadFiles':
            return i18n.t('fileExplorer.actions.pickUpload');
        case 'uploadFolder':
            return i18n.t('fileExplorer.actions.pickUploadFolder');
    }
};

const toFileExplorerViewMode = (mode: string): FileExplorerViewMode => {
    if (mode === 'list' || mode === 'icons') {
        return mode;
    }
    throw new Error('Resolved File Explorer view mode is invalid');
};

const resolveFileExplorerInitialViewMode = (): FileExplorerViewMode => {
    const prefersIcons = measureLayoutViewport().width <= 640;
    return toFileExplorerViewMode(
        resolveInitialViewMode({
            storageKey: VIEW_MODE_STORAGE_KEY,
            allowedModes: ['list', 'icons'],
            fallback: prefersIcons ? 'icons' : 'list'
        })
    );
};

const buildSortAction = (initialViewMode: FileExplorerViewMode, sortState: FileExplorerSortState): HeaderActionDefinition => ({
    type: 'custom',
    html: renderSortControl(createFileExplorerSortControlDefinition(sortState, initialViewMode !== 'icons'))
});

const buildViewModeAction = (dependencies: FileExplorerHeaderWidgetDependencies, initialViewMode: FileExplorerViewMode): HeaderActionDefinition => {
    const viewModeIconName: IconName = initialViewMode === 'icons' ? 'dashboard' : 'view-list';
    const viewModeLabel = initialViewMode === 'icons' ? i18n.t('fileExplorer.actions.iconView') : i18n.t('fileExplorer.actions.listView');
    return {
        type: 'button',
        content: uiHtml`${dependencies.getIconSync(viewModeIconName, { size: 24, strokeWidth: 1.5 })}<span>${viewModeLabel}</span>`,
        variant: 'ui-variant-neutral',
        class: 'file-explorer-view-mode-toggle',
        attributes: { 'data-action': FILE_EXPLORER_ACTION_TOGGLE_VIEW_MODE, id: 'file-explorer-view-mode-toggle', 'aria-pressed': initialViewMode === 'icons' ? 'true' : 'false' },
        ariaLabel: viewModeLabel
    };
};

const buildNewEntryAction = (dependencies: FileExplorerHeaderWidgetDependencies): HeaderActionDefinition => ({
    type: 'filter',
    class: 'ui-variant-accent file-explorer-new-entry-shell',
    filter: {
        type: 'select',
        id: 'file-explorer-new-entry',
        icon: dependencies.getIconSync('add', { size: 24, strokeWidth: 1.5 }),
        attributes: {
            'data-action': FILE_EXPLORER_ACTION_NEW_ENTRY,
            'data-page-actions-menu-close-on-change': 'true',
            'aria-label': i18n.t('fileExplorer.actions.newEntryLabel')
        },
        options: FILE_EXPLORER_NEW_ENTRY_OPTION_VALUES.map((value) => ({ value, label: resolveNewEntryLabel(value) }))
    }
});

const renderFileExplorerHeaderWidget = (dependencies: FileExplorerHeaderWidgetDependencies): FileExplorerHeaderWidgetResult => {
    const initialViewMode = resolveFileExplorerInitialViewMode();
    const header = dependencies.generateStandardHeader({
        title: i18n.t('pages.fileExplorer.title'),
        description: i18n.t('pages.fileExplorer.description'),
        floating: true,
        contentAreaClass: 'file-explorer-content',
        actions: [buildSortAction(initialViewMode, dependencies.sortState), ...buildFileExplorerCommandActions(dependencies), buildViewModeAction(dependencies, initialViewMode), buildNewEntryAction(dependencies)],
        toolbars: {
            id: 'file-explorer-chrome',
            ariaLabel: i18n.t('fileExplorer.aria.chrome'),
            html: renderFileExplorerAddressBar({ getIconSync: dependencies.getIconSync })
        }
    });
    return { header, initialViewMode };
};

export { renderFileExplorerHeaderWidget };
export type { FileExplorerHeaderWidgetDependencies };
