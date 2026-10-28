/* SoAI - Shared collection notice and empty state presentation [frontend/assets/ts/core/ui/collectionFeedback.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { reconcileChildNodes, reconcileRepeatedElementChildrenFromTrustedHtml } from '@core/dom/childNodeReconciliation.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';

type CollectionNoticeTone = 'info' | 'warning' | 'error';

interface CollectionNotice {
    readonly tone: CollectionNoticeTone;
    readonly title: string;
    readonly detail: string;
    readonly actions: readonly HTMLButtonElement[];
}

interface CollectionEmptyState {
    readonly icon: IconName;
    readonly title: string;
    readonly message: string;
}

const NOTICE_ICONS: Readonly<Record<CollectionNoticeTone, IconName>> = { info: 'info', warning: 'warning', error: 'error' };

const createCollectionNoticeAction = (documentValue: Document, action: string, label: string): HTMLButtonElement => {
    const button = documentValue.createElement('button');
    button.type = 'button';
    button.className = 'ui-button ui-button--sm';
    button.dataset['action'] = action;
    button.setAttribute('aria-label', label);
    button.dataset['tooltip'] = label;
    button.textContent = label;
    return button;
};

const renderCollectionNotice = (surface: HTMLElement, notice: CollectionNotice | null): void => {
    const toneClassName = notice && notice.tone !== 'info' ? ` ui-collection-notice--${notice.tone}` : '';
    surface.className = `ui-collection-notice glass-surface-medium${notice ? toneClassName : ' u-hidden'}`;
    if (!notice) {
        surface.replaceChildren();
        return;
    }
    const documentValue = surface.ownerDocument;
    const indicator = createIconSlot(documentValue, getIconSync(NOTICE_ICONS[notice.tone], { size: 20, strokeWidth: 1.7 }), { className: 'ui-collection-notice__icon' });
    const copy = documentValue.createElement('div');
    copy.className = 'ui-collection-notice__copy';
    const title = documentValue.createElement('strong');
    title.textContent = notice.title;
    const detail = documentValue.createElement('span');
    detail.textContent = notice.detail;
    copy.append(title, detail);
    const children: HTMLElement[] = [indicator, copy];
    if (notice.actions.length > 0) {
        const actions = documentValue.createElement('div');
        actions.className = 'ui-collection-notice__actions';
        actions.append(...notice.actions);
        children.push(actions);
    }
    reconcileChildNodes(surface, children);
};

const renderCollectionEmptyState = (surface: HTMLElement, emptyState: CollectionEmptyState | null): void => {
    surface.classList.toggle('u-hidden', emptyState === null);
    if (!emptyState) return;
    reconcileRepeatedElementChildrenFromTrustedHtml({
        target: surface,
        html: renderEmptyState({
            icon: getIconSync(emptyState.icon),
            title: emptyState.title,
            message: emptyState.message,
            className: 'ui-empty-state ui-collection-empty glass-surface-medium',
            iconClassName: 'ui-empty-state__icon ui-collection-empty__icon'
        })
    });
};

export { createCollectionNoticeAction, renderCollectionEmptyState, renderCollectionNotice };
export type { CollectionEmptyState, CollectionNotice, CollectionNoticeTone };
