/* SoAI - Shared UI labels [frontend/assets/ts/core/ui/modals/contentpreview/labels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ContentPreviewButtonLabels, ContentPreviewScope } from '@core/ui/modals/contentpreview/types.ts';

const resolveSharedLabels = (): { close: string; cancel: string; openSource: string } => {
    return {
        close: i18n.t('common.close'),
        cancel: i18n.t('common.cancel'),
        openSource: i18n.t('contentPreview.actions.openSource')
    };
};

const resolveChatLabels = (): ContentPreviewButtonLabels =>
    Object.freeze({
        ...resolveSharedLabels(),
        download: i18n.t('fileExplorer.modal.download'),
        copy: i18n.t('common.copy'),
        attach: i18n.t('contentPreview.actions.attach'),
        edit: i18n.t('common.edit'),
        save: i18n.t('common.save'),
        enhance: i18n.t('common.ok'),
        emptyCopyTitle: i18n.t('common.copy'),
        emptyDownloadTitle: i18n.t('fileExplorer.modal.download')
    });

const resolveFileExplorerLabels = (): ContentPreviewButtonLabels =>
    Object.freeze({
        ...resolveSharedLabels(),
        download: i18n.t('fileExplorer.modal.download'),
        copy: i18n.t('fileExplorer.modal.copy'),
        attach: i18n.t('contentPreview.actions.attach'),
        edit: i18n.t('fileExplorer.modal.edit'),
        save: i18n.t('fileExplorer.modal.save'),
        enhance: i18n.t('common.ok'),
        emptyCopyTitle: i18n.t('fileExplorer.modal.copy'),
        emptyDownloadTitle: i18n.t('fileExplorer.modal.download')
    });

const resolvePromptsLabels = (): ContentPreviewButtonLabels =>
    Object.freeze({
        ...resolveSharedLabels(),
        download: i18n.t('prompts.actions.download'),
        copy: i18n.t('prompts.actions.copy'),
        attach: i18n.t('contentPreview.actions.attach'),
        edit: i18n.t('prompts.modal.viewPrompt.edit'),
        save: i18n.t('prompts.modal.viewPrompt.save'),
        enhance: i18n.t('prompts.enhancer.actions.enhance'),
        emptyCopyTitle: i18n.t('prompts.notifications.emptyPromptCopy'),
        emptyDownloadTitle: i18n.t('prompts.notifications.emptyPromptDownload')
    });

const resolveContentPreviewButtonLabels = (scope: ContentPreviewScope): ContentPreviewButtonLabels => {
    if (scope === 'chat') {
        return resolveChatLabels();
    }
    if (scope === 'fileExplorer') {
        return resolveFileExplorerLabels();
    }
    return resolvePromptsLabels();
};

export { resolveContentPreviewButtonLabels };
