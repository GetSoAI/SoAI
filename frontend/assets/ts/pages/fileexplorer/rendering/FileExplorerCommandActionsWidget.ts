/* SoAI - File Explorer header command action definitions [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerCommandActionsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { HeaderActionDefinition, HeaderActionVariant } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { FILE_EXPLORER_ACTION_COPY_HERE, FILE_EXPLORER_ACTION_MODE_CANCEL, FILE_EXPLORER_ACTION_MOVE_HERE, FILE_EXPLORER_ACTION_SELECTION_COPY, FILE_EXPLORER_ACTION_SELECTION_DELETE, FILE_EXPLORER_ACTION_SELECTION_DESELECT_ALL, FILE_EXPLORER_ACTION_SELECTION_DOWNLOAD, FILE_EXPLORER_ACTION_SELECTION_INVERSE, FILE_EXPLORER_ACTION_SELECTION_METADATA, FILE_EXPLORER_ACTION_SELECTION_MOVE, FILE_EXPLORER_ACTION_SELECTION_RENAME, FILE_EXPLORER_ACTION_SELECTION_SELECT_ALL, FILE_EXPLORER_ACTION_SELECTION_SOAI_LINK, FILE_EXPLORER_ACTION_TOGGLE_SELECTION_MODE } from '@features/fileexplorer/public.ts';

interface FileExplorerCommandActionsDependencies {
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
}

interface FileExplorerCommandAction {
    id: string;
    action: string;
    icon: IconName;
    label: string;
    variant?: HeaderActionVariant;
}

const ICON_OPTIONS: IconOptions = { size: 24, strokeWidth: 1.5 };

const commandActions = (): readonly FileExplorerCommandAction[] => [
    { id: 'file-explorer-selection-select-all', action: FILE_EXPLORER_ACTION_SELECTION_SELECT_ALL, icon: 'check', label: i18n.t('fileExplorer.actions.selectAll'), variant: 'ui-variant-neutral' },
    { id: 'file-explorer-selection-deselect-all', action: FILE_EXPLORER_ACTION_SELECTION_DESELECT_ALL, icon: 'minus', label: i18n.t('fileExplorer.actions.deselectAll'), variant: 'ui-variant-neutral' },
    { id: 'file-explorer-selection-inverse', action: FILE_EXPLORER_ACTION_SELECTION_INVERSE, icon: 'modified', label: i18n.t('fileExplorer.actions.selectInverse'), variant: 'ui-variant-neutral' },
    { id: 'file-explorer-selection-metadata', action: FILE_EXPLORER_ACTION_SELECTION_METADATA, icon: 'info', label: i18n.t('fileExplorer.actionBar.metadata.single'), variant: 'ui-variant-neutral' },
    { id: 'file-explorer-selection-rename', action: FILE_EXPLORER_ACTION_SELECTION_RENAME, icon: 'rename', label: i18n.t('fileExplorer.actions.rename') },
    { id: 'file-explorer-selection-soai-link', action: FILE_EXPLORER_ACTION_SELECTION_SOAI_LINK, icon: 'paperclip', label: i18n.t('fileExplorer.actionBar.use.single'), variant: 'ui-variant-violet' },
    { id: 'file-explorer-selection-copy', action: FILE_EXPLORER_ACTION_SELECTION_COPY, icon: 'copy', label: i18n.t('fileExplorer.actionBar.copy.single'), variant: 'ui-variant-primary' },
    { id: 'file-explorer-selection-move', action: FILE_EXPLORER_ACTION_SELECTION_MOVE, icon: 'arrow-right', label: i18n.t('fileExplorer.actionBar.move.single'), variant: 'ui-variant-warning' },
    { id: 'file-explorer-selection-delete', action: FILE_EXPLORER_ACTION_SELECTION_DELETE, icon: 'delete', label: i18n.t('fileExplorer.actionBar.delete.single'), variant: 'ui-variant-danger' },
    { id: 'file-explorer-selection-download', action: FILE_EXPLORER_ACTION_SELECTION_DOWNLOAD, icon: 'download', label: i18n.t('fileExplorer.actionBar.download.single'), variant: 'ui-variant-accent' },
    { id: 'file-explorer-copy-here', action: FILE_EXPLORER_ACTION_COPY_HERE, icon: 'copy', label: i18n.t('fileExplorer.actionBar.copyHere.single'), variant: 'ui-variant-primary' },
    { id: 'file-explorer-move-here', action: FILE_EXPLORER_ACTION_MOVE_HERE, icon: 'arrow-right', label: i18n.t('fileExplorer.actionBar.moveHere.single'), variant: 'ui-variant-warning' },
    { id: 'file-explorer-transfer-cancel', action: FILE_EXPLORER_ACTION_MODE_CANCEL, icon: 'close', label: i18n.t('common.cancel'), variant: 'ui-variant-neutral' }
];

const buildSelectionModeToggle = (dependencies: FileExplorerCommandActionsDependencies): HeaderActionDefinition => ({
    type: 'button',
    id: 'file-explorer-toggle-selection-mode',
    class: 'toggle-selection-mode u-hidden',
    ariaLabel: i18n.t('fileExplorer.actions.toggleSelectionMode'),
    attributes: { 'data-action': FILE_EXPLORER_ACTION_TOGGLE_SELECTION_MODE, 'aria-pressed': 'false' },
    content: uiHtml`<span class="toggle-selection-mode-open-icon" aria-hidden="true">${dependencies.getIconSync('select', ICON_OPTIONS)}</span><span class="toggle-selection-mode-label" data-button-text>${uiText(i18n.t('fileExplorer.actions.selectionToggleLabel'))}</span><span class="toggle-selection-mode-close-icon" aria-hidden="true">${dependencies.getIconSync('close', ICON_OPTIONS)}</span>`
});

const toHeaderAction = (dependencies: FileExplorerCommandActionsDependencies, command: FileExplorerCommandAction): HeaderActionDefinition => {
    const showsLabel = command.action !== FILE_EXPLORER_ACTION_MODE_CANCEL;
    return {
        type: 'button',
        id: command.id,
        ...(command.variant ? { variant: command.variant } : {}),
        class: showsLabel ? 'file-explorer-labeled-command u-hidden' : 'u-hidden',
        ariaLabel: command.label,
        attributes: { 'data-action': command.action },
        content: uiHtml`${dependencies.getIconSync(command.icon, ICON_OPTIONS)}<span data-button-text>${uiText(command.label)}</span>`
    };
};

const buildFileExplorerCommandActions = (dependencies: FileExplorerCommandActionsDependencies): HeaderActionDefinition[] => [buildSelectionModeToggle(dependencies), ...commandActions().map((command) => toHeaderAction(dependencies, command))];

export { buildFileExplorerCommandActions };
