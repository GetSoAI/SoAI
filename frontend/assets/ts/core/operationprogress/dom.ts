/* SoAI - Shared operation progress DOM contracts [frontend/assets/ts/core/operationprogress/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { syncDeterminateProgress } from '@core/ui/progressWidths.ts';

const resolveCancelIconMarkup = (): TrustedHtml => {
    return getIconSync('close', {
        strokeWidth: 1.5,
        attributes: { 'aria-hidden': 'true', focusable: 'false' }
    });
};

const createProgressElement = (key: string, message: string, options: { showCancel?: boolean; showBadge?: boolean; extraClassName?: string | null } = {}): HTMLElement => {
    const { showCancel = true, showBadge = true, extraClassName = null } = options;
    const progressElement = dom.getDocument().createElement('div');
    dom.addClass(progressElement, 'ui-operation-progress');
    if (extraClassName) {
        dom.addClass(progressElement, extraClassName);
        dom.setData(progressElement, 'extraClassName', extraClassName);
    }
    dom.setData(progressElement, 'operationProgressKey', key);

    const cancelButton = showCancel
        ? (() => {
              const cancelIcon = resolveCancelIconMarkup();
              const cancelLabel = i18n.t('common.cancel');
              return uiHtml`<button type="button" class="ui-round-button ui-round-button--delete" data-operation-progress-action="cancel" aria-label="${uiAttr(cancelLabel)}" data-tooltip="${uiAttr(cancelLabel)}">${renderIconSlot(cancelIcon)}</button>`;
          })()
        : EMPTY_UI_HTML;
    const badgeSlot = showBadge ? uiHtml`<span class="ui-operation-progress__badge" hidden></span>` : EMPTY_UI_HTML;

    dom.setHTML(
        progressElement,
        uiHtml`<div class="ui-operation-progress__header"><span class="ui-operation-progress__message">${message}</span>${badgeSlot}${cancelButton}</div>
          <div>
              <div class="ui-operation-progress__bar progress-bar">
                  <div class="ui-operation-progress__fill progress-fill"></div>
              </div>
          </div>
          <div class="ui-operation-progress__info">
              <div class="ui-operation-progress__details"></div>
              <div class="ui-operation-progress__percentage">0%</div>
          </div>`,
        { escape: false }
    );

    return progressElement;
};

const updateProgressElement = (element: HTMLElement, progress: number | undefined, message: string | undefined, badge: string | undefined, details: string | undefined, state: 'success' | 'error' | 'downloading' | 'pending' | 'info' | undefined, cancelable: boolean | undefined): void => {
    const messageElement = dom.resolve('.ui-operation-progress__message', element);
    const badgeElement = dom.resolve('.ui-operation-progress__badge', element);
    const fillElement = dom.resolve('.ui-operation-progress__fill', element);
    const detailsElement = dom.resolve('.ui-operation-progress__details', element);
    const percentageElement = dom.resolve('.ui-operation-progress__percentage', element);
    const cancelButton = dom.resolve('button[data-operation-progress-action="cancel"]', element);

    if (messageElement && message !== undefined) {
        dom.setText(messageElement, message);
    }

    if (badgeElement instanceof HTMLElement && badge !== undefined) {
        const normalizedBadge = badge.trim();
        dom.setText(badgeElement, normalizedBadge);
        badgeElement.hidden = !normalizedBadge;
    }

    if (fillElement && progress !== undefined) {
        syncDeterminateProgress({
            fillElement,
            progress,
            valueElement: percentageElement,
            syncUsageClass: true
        });
    }

    if (detailsElement && details !== undefined) {
        dom.setText(detailsElement, details);
    }

    if (state !== undefined) {
        const currentClasses = dom.getClasses(element);
        if (currentClasses.length) {
            dom.removeClass(element, currentClasses);
        }
        const extraClassName = dom.getData(element, 'extraClassName');
        dom.addClass(element, extraClassName ? ['ui-operation-progress', extraClassName, `ui-operation-progress--${state}`] : ['ui-operation-progress', `ui-operation-progress--${state}`]);
    }

    if (cancelButton instanceof HTMLButtonElement && cancelable !== undefined) {
        const enabled = cancelable && cancelButton.dataset['cancelRequested'] !== '1';
        cancelButton.hidden = !enabled;
        cancelButton.disabled = !enabled;
        cancelButton.setAttribute('aria-disabled', enabled ? 'false' : 'true');
    }
};

export { createProgressElement, updateProgressElement };
