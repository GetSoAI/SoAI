/* SoAI - Shared page outlet DOM contracts [frontend/assets/ts/core/pageoutlet/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom, resolve } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { isHTMLElement, isString } from '@core/typeGuards.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import type { PageOutletOverlayElements, PageOutletStateOptions } from '@core/pageoutlet/types.ts';

const resolveContainer = (target: HTMLElement | string): HTMLElement => {
    if (isHTMLElement(target)) {
        return target;
    }
    if (!isString(target)) {
        throw new Error('PageOutlet requires a container target');
    }

    const trimmed = target.trim();
    if (!trimmed) {
        throw new Error('PageOutlet requires a valid container selector');
    }

    const scope = dom.getDocument();
    const direct = trimmed.startsWith('#') || trimmed.startsWith('.') ? resolve(trimmed, scope) : null;
    if (isHTMLElement(direct)) {
        return direct;
    }

    const withHash = resolve(`#${trimmed}`, scope);
    if (isHTMLElement(withHash)) {
        return withHash;
    }

    throw new Error('PageOutlet could not resolve the container element');
};

const createOverlayElements = (container: HTMLElement, overlayAddRetryListener: (button: HTMLButtonElement) => void): PageOutletOverlayElements => {
    const doc = container.ownerDocument ?? dom.getDocument();
    const overlay = doc.createElement('div');
    overlay.className = 'page-outlet-overlay u-hidden';
    overlay.dataset['pageOutletSlot'] = 'overlay';
    overlay.setAttribute('aria-live', 'polite');
    overlay.hidden = true;

    const panel = doc.createElement('div');
    panel.className = 'page-outlet-overlay-panel';

    const spinner = doc.createElement('div');
    spinner.className = 'page-outlet-overlay-spinner';
    spinner.setAttribute('aria-hidden', 'true');

    const label = doc.createElement('p');
    label.className = 'page-outlet-overlay-label';

    const detail = doc.createElement('p');
    detail.className = 'page-outlet-overlay-detail';

    const action = doc.createElement('button');
    action.type = 'button';
    action.className = 'ui-button ui-variant-accent page-outlet-overlay-action u-hidden';
    action.hidden = true;
    action.textContent = '';

    panel.append(spinner, label, detail, action);
    overlay.append(panel);
    container.append(overlay);
    overlayAddRetryListener(action);

    return {
        overlay,
        overlayLabel: label,
        overlayDetail: detail,
        overlayAction: action
    };
};

const showOverlay = (overlayElements: PageOutletOverlayElements, mode: string, label: string | null, detail: string | null, showRetryAction: boolean, delayed: boolean): void => {
    const { overlay, overlayLabel, overlayDetail, overlayAction } = overlayElements;
    overlay.hidden = false;
    overlay.classList.remove('u-hidden', 'is-error', 'is-loading', 'is-loading-delayed');
    overlay.classList.add(mode === 'error' ? 'is-error' : 'is-loading');
    overlay.classList.toggle('is-loading-delayed', mode === 'loading' && delayed);
    setAriaBusy(overlay, mode === 'loading');
    overlayLabel.textContent = label ?? '';
    overlayDetail.textContent = mode === 'error' ? (detail ?? '') : '';
    overlayDetail.classList.remove('form-disclaimer', 'form-disclaimer-error');
    if (mode === 'loading' && detail) {
        overlayDetail.textContent = detail;
        overlayDetail.classList.add('form-disclaimer', 'form-disclaimer-error');
    }

    overlayAction.classList.toggle('u-hidden', !showRetryAction);
    overlayAction.hidden = !showRetryAction;
    if (showRetryAction) {
        overlayAction.textContent = i18n.t('pageOutlet.retry');
    }
};

const hideOverlay = (overlayElements: PageOutletOverlayElements | null): void => {
    if (!overlayElements) {
        return;
    }
    const { overlay, overlayLabel, overlayDetail, overlayAction } = overlayElements;
    overlay.classList.remove('is-error', 'is-loading', 'is-loading-delayed');
    overlay.hidden = true;
    overlay.classList.add('u-hidden');
    overlayLabel.textContent = '';
    overlayDetail.textContent = '';
    overlayDetail.classList.remove('form-disclaimer', 'form-disclaimer-error');
    overlayAction.textContent = '';
    overlayAction.hidden = true;
    overlayAction.classList.add('u-hidden');
};

interface PageOutletDomStateOptions extends PageOutletStateOptions {
    state: string;
    container: HTMLElement;
    overlayElements: PageOutletOverlayElements | null;
    ensureOverlay: () => PageOutletOverlayElements;
    clearSkeleton: () => void;
    hasRetryHandler: boolean;
}

const setPageOutletState = ({ state, label = null, detail = null, delayed = false, container, overlayElements, ensureOverlay, clearSkeleton, hasRetryHandler }: PageOutletDomStateOptions): PageOutletOverlayElements | null => {
    if (state && state !== 'ready') {
        container.dataset['pageOutletState'] = state;
    } else {
        delete container.dataset['pageOutletState'];
    }

    if (state === 'loading') {
        setAriaBusy(container, true);
        const resolvedOverlay = ensureOverlay();
        showOverlay(resolvedOverlay, 'loading', label, detail, false, delayed);
        return resolvedOverlay;
    }

    setAriaBusy(container, false);
    if (state === 'error') {
        const resolvedOverlay = ensureOverlay();
        showOverlay(resolvedOverlay, 'error', label, detail, hasRetryHandler, false);
        return resolvedOverlay;
    }

    clearSkeleton();
    hideOverlay(overlayElements);
    return overlayElements;
};

export { createOverlayElements, hideOverlay, resolveContainer, setPageOutletState, showOverlay };
