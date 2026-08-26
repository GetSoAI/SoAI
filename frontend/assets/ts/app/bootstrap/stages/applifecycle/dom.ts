/* SoAI - Frontend application lifecycle DOM contracts [frontend/assets/ts/app/bootstrap/stages/applifecycle/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { querySelectorStrict } from '@app/bootstrap/stages/appLifecycleSupport.ts';
import { getDiscoveryService } from '@core/discoveryservice/public.ts';
import { dom } from '@core/dom/dom.ts';
import { getElementByIdStrict, requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError, extractErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isBackendEditionIntegrityError } from '@core/edition/backendEditionIntegrity.ts';
import type { StateManager } from '@core/state/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { isArray, isInstanceOf, isThenable } from '@core/typeGuards.ts';

export const prepareLifecycleEnvironment = (): void => {
    const body = requireDocument().body;
    if (!body) {
        throw new Error('Document body must be available to prepare UI');
    }
    dom.addClass(body, ['ui-ready', 'ui-animated']);
};

export const toggleMainUIVisibility = (show: boolean, stateManager: StateManager): void => {
    const elements = ['.header', '.sidebar'].map((selector) => {
        const element = querySelectorStrict(selector);
        if (!isInstanceOf(element, HTMLElement)) {
            throw new Error(`Element for selector ${selector} must be an HTMLElement`);
        }
        return element;
    });

    elements.forEach((element) => {
        if (show) {
            dom.removeClass(element, 'u-hidden');
            dom.setStyles(element, { display: '', visibility: '' });
        } else {
            dom.addClass(element, 'u-hidden');
            dom.setStyle(element, 'display', 'none');
        }
    });

    stateManager.toggleHidden(elements, !show);
    if (show) {
        const body = requireDocument().body;
        if (body) {
            dom.removeClass(body, ['page-login', 'page-wizard']);
        }
    }
};

export const renderLifecycleInitializationError = (error: Error, finalizePreloader: () => void | Promise<void>): void => {
    try {
        const result = finalizePreloader();
        if (isThenable(result)) {
            void Promise.resolve(result).catch((preloaderError: Error) => {
                const runtimeError = ensureError(preloaderError);
                errorHandler.warn('AppLifecycle', 'Failed to finalize preloader during error rendering', runtimeError);
            });
        }
    } catch (preloaderError) {
        const runtimeError = ensureError(preloaderError);
        errorHandler.warn('AppLifecycle', 'Failed to finalize preloader during error rendering', runtimeError);
    }

    const container = getElementByIdStrict('app');
    const editionIntegrityFailure = isBackendEditionIntegrityError(error);
    const message = editionIntegrityFailure ? i18n.t('app.errors.editionIntegrity.message') : (extractErrorMessage(error) ?? i18n.t('app.errors.unknown'));
    const normalized = message.toLowerCase();
    const discoveryError = normalized.includes('discovery') || normalized.includes('port discovery') || normalized.includes('backend discovery failed');

    let detailsMarkup = EMPTY_UI_HTML;
    if (discoveryError) {
        const ports = getDiscoveryService().getCandidatePorts();
        if (!isArray(ports)) {
            throw new Error('Discovery service must return an array of ports');
        }
        const items = [
            i18n.t('app.errors.discoveryHelp.items.backendRunning'),
            i18n.t('app.errors.discoveryHelp.items.discoveryReachable', {
                ports: ports.length ? ports.join(', ') : i18n.t('app.errors.discoveryHelp.defaultPorts')
            }),
            i18n.t('app.errors.discoveryHelp.items.noFirewall')
        ]
            .map((item) => uiHtml`<li>${item}</li>`.html)
            .join('');
        detailsMarkup = uiHtml`<p><strong>${i18n.t('app.errors.discoveryHelp.heading')}</strong></p><ul>${toTrustedUiHtml(items)}</ul>`;
    }

    const title = editionIntegrityFailure ? i18n.t('app.errors.editionIntegrity.title') : i18n.t('app.errors.initFailed');
    const reloadLabel = i18n.t('common.actions.reloadPage');
    dom.setHTML(
        container,
        uiHtml`
            <div class="initialization-error" role="alert" aria-live="polite">
                <div class="initialization-error__card glass-surface-light">
                    <div class="initialization-error__top">
                        <div class="initialization-error__badge" aria-hidden="true">!</div>
                        <div class="initialization-error__heading">
                            <h1>${title}</h1>
                            <p class="initialization-error__message">${message}</p>
                        </div>
                    </div>

                    <div class="initialization-error__details">${detailsMarkup}</div>

                    <div class="initialization-error__actions">
                        <button
                            type="button"
                            class="ui-button ui-variant-accent"
                            data-lifecycle-reload
                            aria-label="${uiAttr(reloadLabel)}"
                            data-tooltip="${uiAttr(reloadLabel)}"
                        >
                            ${reloadLabel}
                        </button>
                    </div>
                </div>
            </div>
        `,
        { escape: false }
    );

    const reloadButton = dom.resolve('[data-lifecycle-reload]', container);
    if (reloadButton) {
        const handleReloadClick = (): void => {
            window.location.reload();
        };
        reloadButton.addEventListener('click', handleReloadClick, { once: true });
    }
};
