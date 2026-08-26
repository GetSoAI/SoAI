/* SoAI - Chat composer draft task failure logging [frontend/assets/ts/features/chat/composerdraft/composerDraftTaskLogging.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ComposerDraftManagerDependencies } from '@features/chat/composerdraft/composerDraftTypes.ts';

const logComposerDraftTaskFailure = (dependencies: ComposerDraftManagerDependencies, message: string, error: Error): void => {
    dependencies.logWarning(message, ensureError(error));
};

const trackComposerDraftTaskFailure = (task: Promise<void>, dependencies: ComposerDraftManagerDependencies, message: string): void => {
    void task.catch((error) => logComposerDraftTaskFailure(dependencies, message, error));
};

const presentComposerDraftRestoreFailure = (dependencies: ComposerDraftManagerDependencies, message: string, error: Error): void => {
    logComposerDraftTaskFailure(dependencies, message, error);
    dependencies.showNotification(i18n.t('chat.draft.restoreFailed'), 'error');
};

export { logComposerDraftTaskFailure, presentComposerDraftRestoreFailure, trackComposerDraftTaskFailure };
