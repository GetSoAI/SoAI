/* SoAI - Frontend application lifecycle DOM contracts [frontend/assets/ts/app/bootstrap/stages/applifecycle/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { animateShellEntrance, cancelShellEntrance } from '@core/layout/shellEntrance.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import { querySelectorStrict } from '@app/bootstrap/stages/appLifecycleSupport.ts';
import { describeInitializationFailure, type InitializationStage } from '@app/bootstrap/stages/initializationStage.ts';
import { clearActiveWallpaperReadiness } from '@core/backgroundtasks/wallpaperReadiness.ts';
import { getDiscoveryService } from '@core/discoveryservice/public.ts';
import { dom } from '@core/dom/dom.ts';
import { getElementByIdStrict, requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveBootMessages } from '@core/languageservice/bootMessages.ts';
import { i18n } from '@core/i18n/index.ts';
import { BackendDiscoveryError } from '@core/discoveryservice/discoveryError.ts';
import { bindReloadFailure } from '@core/ui/reloadFailure.ts';
import { isBackendEditionIntegrityError } from '@core/edition/backendEditionIntegrity.ts';
import type { StateManager } from '@core/state/public.ts';
import { EMPTY_UI_HTML, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { isArray, isInstanceOf, isThenable } from '@core/typeGuards.ts';

const describeInitializationStage = (stage: InitializationStage | null, messages: ReturnType<typeof resolveBootMessages>): string => {
    switch (stage) {
        case 'entrypoint':
            return i18n.t('app.errors.stages.entrypoint', undefined, messages);
        case 'criticalServices':
            return i18n.t('app.errors.stages.criticalServices', undefined, messages);
        case 'authentication':
            return i18n.t('app.errors.stages.authentication', undefined, messages);
        case 'session':
            return i18n.t('app.errors.stages.session', undefined, messages);
        case 'routeRendering':
            return i18n.t('app.errors.stages.routeRendering', undefined, messages);
        case 'background':
            return i18n.t('app.errors.stages.background', undefined, messages);
        case null:
            return i18n.t('app.errors.unknown', undefined, messages);
    }
};

export const prepareLifecycleEnvironment = (): void => {
    const body = requireDocument().body;
    if (!body) {
        throw new Error('Document body must be available to prepare UI');
    }
    dom.addClass(body, ['ui-ready', 'ui-animated']);
};

export const toggleMainUIVisibility = (show: boolean, stateManager: StateManager, animateEntrance = false): void => {
    const elements = ['.header', '.sidebar'].map((selector) => {
        const element = querySelectorStrict(selector);
        if (!isInstanceOf(element, HTMLElement)) {
            throw new Error(`Element for selector ${selector} must be an HTMLElement`);
        }
        return element;
    });

    if (!show) cancelShellEntrance(elements);
    elements.forEach((element) => {
        if (show) {
            dom.removeClass(element, 'u-hidden');
            dom.setStyle(element, 'visibility', '');
        } else {
            dom.addClass(element, 'u-hidden');
        }
    });

    stateManager.toggleHidden(elements, !show);
    if (show) {
        const body = requireDocument().body;
        if (body) {
            dom.removeClass(body, ['page-login', 'page-wizard']);
        }
        if (animateEntrance) animateShellEntrance(elements);
    }
};

export const renderLifecycleInitializationError = (error: Error, finalizePreloader: () => void | Promise<void>, options: { surface?: 'main' | 'detached'; missingPage?: boolean } = {}): void => {
    clearActiveWallpaperReadiness();
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

    const detached = options.surface === 'detached';
    const container = getElementByIdStrict(detached ? 'main-content' : 'app');
    const messages = resolveBootMessages();
    container.lang = messages.language;
    container.dir = messages.direction;
    const editionIntegrityFailure = isBackendEditionIntegrityError(error);
    const failure = describeInitializationFailure(error);
    const message = editionIntegrityFailure ? i18n.t('app.errors.editionIntegrity.message', undefined, messages) : options.missingPage ? i18n.t('app.detachedWindow.errors.noPageSpecified', undefined, messages) : detached ? i18n.t('app.detachedWindow.errors.initializationFailed', undefined, messages) : describeInitializationStage(failure.stage, messages);
    const discoveryError = error instanceof BackendDiscoveryError;

    let detailsMarkup = EMPTY_UI_HTML;
    if (discoveryError) {
        let ports: number[] = [];
        try {
            ports = getDiscoveryService().getCandidatePorts();
        } catch (discoveryServiceError) {
            errorHandler.debug('AppLifecycle', 'Discovery guidance uses default ports before service readiness', ensureError(discoveryServiceError));
        }
        if (!isArray(ports)) {
            throw new Error('Discovery service must return an array of ports');
        }
        const items = [
            i18n.t('app.errors.discoveryHelp.items.backendRunning', undefined, messages),
            i18n.t(
                'app.errors.discoveryHelp.items.discoveryReachable',
                {
                    ports: ports.length ? ports.join(', ') : i18n.t('app.errors.discoveryHelp.defaultPorts', undefined, messages)
                },
                messages
            ),
            i18n.t('app.errors.discoveryHelp.items.noFirewall', undefined, messages)
        ]
            .map((item) => uiHtml`<li>${item}</li>`.html)
            .join('');
        detailsMarkup = uiHtml`<p><strong>${i18n.t('app.errors.discoveryHelp.heading', undefined, messages)}</strong></p><ul>${toTrustedUiHtml(items)}</ul>`;
    }

    const title = editionIntegrityFailure ? i18n.t('app.errors.editionIntegrity.title', undefined, messages) : detached ? i18n.t('detached.errors.initFailed', undefined, messages) : i18n.t('app.errors.initFailed', undefined, messages);
    const reloadLabel = i18n.t('common.actions.reloadPage', undefined, messages);
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

                    <div class="initialization-error__details">
                        ${detailsMarkup}
                        <p>${i18n.t('app.errors.reference', { reference: failure.reference }, messages)}</p>
                    </div>

                    <div class="initialization-error__actions">
                        <button
                            type="button"
                            class="ui-button ui-variant-accent"
                            data-action="reload-page"
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

    const root = dom.resolve('.initialization-error', container);
    if (!(root instanceof HTMLElement)) throw new Error('Initialization error surface is missing');
    bindReloadFailure(root);
};
