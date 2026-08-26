/* SoAI - Settings page backup progress widget [frontend/assets/ts/pages/settings/controllers/backupmanager/backupProgressWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { i18n } from '@core/i18n/index.ts';
import type { BackupOperationState } from '@core/settings/contracts.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { renderOperationProgress } from '@core/ui/operationProgress.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { optionalHTMLElement } from '@pages/settings/controllers/backupmanager/dom.ts';
import { resolveBackupProgressLabel } from '@pages/settings/controllers/backupmanager/backupOperationMessagesController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type BackupProgressWidgetHost = PageDomOwnerHost;

const PROGRESS_TRACKED_BACKUP_TYPES: ReadonlySet<BackupOperationState['type']> = new Set<BackupOperationState['type']>(['create', 'restore']);

class BackupProgressWidget {
    readonly #host: BackupProgressWidgetHost;
    readonly #isMounted: () => boolean;
    readonly #renderQueue: AnimationFrameRenderQueue<BackupOperationState | null>;
    constructor({ host, isMounted }: { host: BackupProgressWidgetHost; isMounted: () => boolean }) {
        this.#host = host;
        this.#isMounted = isMounted;
        this.#renderQueue = new AnimationFrameRenderQueue({
            label: 'BackupProgressWidget',
            render: (operation) => this.#applyOperation(operation),
            merge: (_previous, next) => next,
            isDisposed: () => !this.#isMounted()
        });
    }

    reset(): void {
        this.#renderQueue.cancel();
    }

    scheduleRender(operation: BackupOperationState | null): void {
        this.#renderQueue.schedule(operation);
    }

    #applyOperation(operation: BackupOperationState | null): void {
        const container = optionalHTMLElement(this.#host, UI_IDS.BACKUP_PROGRESS);
        if (!container) {
            return;
        }
        const trackedOperation = operation && PROGRESS_TRACKED_BACKUP_TYPES.has(operation.type) ? operation : null;
        const markup = trackedOperation
            ? renderOperationProgress({
                  label: resolveBackupProgressLabel(trackedOperation.type),
                  state: 'running',
                  percent: trackedOperation.progress,
                  detail: trackedOperation.message,
                  statusText: i18n.t('settings.operationProgress.running')
              })
            : EMPTY_UI_HTML;
        this.#host.pageDom.updateHtml(container, markup, { escape: false });
        this.#host.pageDom.flush();
    }
}

export { BackupProgressWidget };
