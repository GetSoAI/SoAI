/* SoAI - Shared file explorer browser folder picker labels [frontend/assets/ts/core/fileexplorerbrowser/folderPickerLabels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { FolderPickerLabels } from '@core/fileexplorerbrowser/folderPickerView.ts';

const buildFolderPickerLabels = (options: { chooseCurrent: string; reset?: string }): FolderPickerLabels => {
    const labels: FolderPickerLabels = {
        currentFolder: i18n.t('common.folderPicker.currentFolder'),
        manualPath: i18n.t('common.folderPicker.manualPath'),
        manualAbsolutePathRequired: i18n.t('common.folderPicker.manualAbsolutePathRequired'),
        loadFailed: i18n.t('common.folderPicker.loadFailed'),
        search: i18n.t('common.folderPicker.search'),
        searchPlaceholder: i18n.t('common.folderPicker.searchPlaceholder'),
        loading: i18n.t('common.folderPicker.loading'),
        searching: i18n.t('common.folderPicker.searching'),
        empty: i18n.t('common.folderPicker.empty'),
        up: i18n.t('common.folderPicker.up'),
        chooseCurrent: options.chooseCurrent,
        cancel: i18n.t('common.cancel')
    };
    if (options.reset) {
        labels.reset = options.reset;
    }
    return labels;
};

export { buildFolderPickerLabels };
