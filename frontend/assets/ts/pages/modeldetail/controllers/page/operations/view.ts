/* SoAI - Model detail page control layer operations rendering [frontend/assets/ts/pages/modeldetail/controllers/page/operations/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createProgressElement, updateProgressElement } from '@core/operationprogress/dom.ts';
import type { ModelDetailOperationsHost } from '@pages/modeldetail/controllers/page/operations/types.ts';

const setModelDetailDeleteBusy = (host: ModelDetailOperationsHost, isBusy: boolean, text: string | null = null): void => {
    const ui = host.ensureUi();
    host.pageDom.updateProperty(ui.deleteModelButton, 'disabled', isBusy);
    if (text) {
        host.pageDom.updateText(ui.deleteModelButton, text);
    }
};

const updateModelDetailDeleteProgress = (host: ModelDetailOperationsHost, options: { show?: boolean; progress?: number | null; message?: string; state?: 'success' | 'error' | 'downloading' | 'pending' | 'info' } = {}): void => {
    const { show = true, progress = null, message = '', state = 'info' } = options;
    const parent = host.pageDom.optionalHTMLElement('.modeldetail-overview-grid');
    if (!parent) {
        if (!show) {
            return;
        }
        throw new Error('ModelDetailPage requires .modeldetail-overview-grid to display delete progress');
    }
    let container = host.pageDom.optionalHTMLElement('[data-operation-progress-key="model-delete-progress"]');
    if (!show) {
        if (container) {
            host.pageDom.remove(container);
        }
        return;
    }
    if (!container) {
        container = createProgressElement('model-delete-progress', message, { showCancel: false });
        host.pageDom.append(parent, container);
    }
    updateProgressElement(container, progress ?? undefined, message, undefined, undefined, state, false);
};

const clearModelDetailDeleteProgressState = (host: ModelDetailOperationsHost): void => {
    setModelDetailDeleteBusy(host, false);
    updateModelDetailDeleteProgress(host, { show: false });
};

export { clearModelDetailDeleteProgressState, setModelDetailDeleteBusy, updateModelDetailDeleteProgress };
