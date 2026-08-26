/* SoAI - Terminal routed page [frontend/assets/ts/pages/terminal/TerminalPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { replaceChildrenFromHtml } from '@core/dom/html.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { i18n } from '@core/i18n/index.ts';
import { registerDirtyStateGuard } from '@core/navigationGuards.ts';
import { closeDetachedRuntimeWindowsByPage, openDetachedRuntimeWindow } from '@core/runtimeenv/public.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import { securityApi, toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isPTYTerminalConnectError, PTYTerminalView, TERMINAL_FONT_SIZE } from '@features/terminal/public.ts';
import { isTerminalActionId, TERMINAL_ACTION_CLEAR, TERMINAL_ACTION_FOCUS, TERMINAL_ACTION_TEXT_DECREASE, TERMINAL_ACTION_TEXT_INCREASE, type TerminalActionId } from '@pages/terminal/actions.ts';
import { requireTerminalUi } from '@pages/terminal/dom.ts';
import { ACTION_ICONS } from '@pages/terminal/rendering/icons.ts';
import { getStoredTerminalFontSize, saveStoredTerminalFontSize } from '@pages/terminal/services/textZoomStorage.ts';
import type { TerminalUiRefs } from '@pages/terminal/types.ts';
import { renderTerminalPageView, renderTerminalUnavailableHtml } from '@pages/terminal/view.ts';

export const PAGE_ID = 'terminal';
export const PAGE_MODULE_ID = 'pages.TerminalPage';

const terminalLogger = createModuleLogger('TerminalPage', { defaultLevel: 'info' });
const log = terminalLogger;

class TerminalPage extends StaticBasePage {
    #ptyView: PTYTerminalView | null = null;
    #navigationGuardCleanup: (() => void) | null = null;
    #detachActionController: HeaderActionController | null = null;
    #ui: TerminalUiRefs | null = null;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject = {}): Promise<JsonObject> {
        const context = await super.beforeRender(parameters);
        return context ?? {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return toTrustedHtml(renderTerminalPageView());
    }

    override async afterRender(_context: RenderContext): Promise<void> {
        this.#ui = requireTerminalUi(this.pageDom);
        this.#insertIcons();
        this.#syncDetachAction();
    }

    #getStoredFontSize(): number {
        return getStoredTerminalFontSize(this.dependencies.storage, TERMINAL_FONT_SIZE.DEFAULT);
    }

    #saveFontSize(fontSize: number): void {
        saveStoredTerminalFontSize(this.dependencies.storage, TERMINAL_FONT_SIZE.DEFAULT, fontSize);
    }

    #syncDetachAction(): void {
        if (this.services.isDetached()) return;
        this.#detachActionController ??= createHeaderActionController({ actionId: 'detach', contextId: 'terminal' });
        this.#detachActionController.show({ onClick: () => this.#openDetachedWindow() });
    }

    #openDetachedWindow(): void {
        closeDetachedRuntimeWindowsByPage(PAGE_ID);
        openDetachedRuntimeWindow(PAGE_ID, { title: i18n.t('pages.terminal.title') });
    }

    async #initializePtyTerminal(signal?: AbortSignal): Promise<void> {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Terminal UI missing');
        }
        const savedFontSize = this.#getStoredFontSize();
        this.#ptyView = new PTYTerminalView({
            container: ui.shell,
            fontSize: savedFontSize,
            onSessionCreated: (sessionId) => {
                log('debug', `PTY session created: ${sessionId}`);
            },
            onSessionClosed: (sessionId, exitCode) => {
                log('debug', `PTY session closed: ${sessionId}, exit code: ${exitCode}`);
                this.#unregisterNavigationGuard();
            },
            onError: (error) => {
                log('error', `PTY error: ${error}`);
            },
            onBusyStateChanged: (busy) => {
                if (busy) {
                    this.#registerNavigationGuard();
                } else {
                    this.#unregisterNavigationGuard();
                }
            }
        });
        await this.#ptyView.mount(signal);
    }

    #handleTerminalInitializeError(error: Error): void {
        const code = isPTYTerminalConnectError(error) ? error.code : null;
        const message = code === 'feature_disabled' ? i18n.t('terminal.unavailable.featureDisabled') : code === 'forbidden_error' ? i18n.t('terminal.unavailable.forbidden') : i18n.t('terminal.unavailable.generic');
        log('warn', 'Terminal initialization failed', { code, error });
        this.#ptyView?.dispose();
        this.#ptyView = null;

        const ui = this.#ui;
        if (!ui) {
            throw new Error('Terminal UI missing');
        }

        const title = i18n.t('terminal.unavailable.title');
        const unavailableHtml = renderTerminalUnavailableHtml({
            title,
            message,
            escapeHtml: (value: string) => securityApi.escapeHtml(value)
        });
        replaceChildrenFromHtml({
            element: ui.shell,
            html: securityApi.sanitizeHtml(unavailableHtml),
            context: ui.shell
        });

        this.#setToolbarDisabled(true);
    }

    #setToolbarDisabled(disabled: boolean): void {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Terminal UI missing');
        }
        const decreaseButton = this.pageDom.requireHTMLElement('#terminal-text-decrease', ui.root);
        const increaseButton = this.pageDom.requireHTMLElement('#terminal-text-increase', ui.root);
        const clearButton = this.pageDom.requireHTMLElement('#terminal-clear', ui.root);

        if (!(decreaseButton instanceof HTMLButtonElement)) {
            throw new TypeError('Terminal decrease button must be a button element');
        }
        if (!(increaseButton instanceof HTMLButtonElement)) {
            throw new TypeError('Terminal increase button must be a button element');
        }
        if (!(clearButton instanceof HTMLButtonElement)) {
            throw new TypeError('Terminal clear button must be a button element');
        }

        this.pageDom.updateProperty(decreaseButton, 'disabled', disabled);
        this.pageDom.updateAttribute(decreaseButton, 'aria-disabled', disabled ? 'true' : 'false');

        this.pageDom.updateProperty(increaseButton, 'disabled', disabled);
        this.pageDom.updateAttribute(increaseButton, 'aria-disabled', disabled ? 'true' : 'false');

        this.pageDom.updateProperty(clearButton, 'disabled', disabled);
        this.pageDom.updateAttribute(clearButton, 'aria-disabled', disabled ? 'true' : 'false');
    }

    #registerNavigationGuard(): void {
        if (this.#navigationGuardCleanup) return;
        this.#navigationGuardCleanup = registerDirtyStateGuard(
            () => {
                if (!this.#ptyView?.busy) return true;
                const message = i18n.t('terminal.confirmations.commandRunning');
                return window.confirm(message);
            },
            { id: 'terminal-command-guard' }
        );
    }

    #unregisterNavigationGuard(): void {
        this.#navigationGuardCleanup?.();
        this.#navigationGuardCleanup = null;
    }

    override async startLiveUpdates(parameters: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.startLiveUpdates(parameters, context);
        try {
            await this.#initializePtyTerminal(context.signal);
            if (context.signal?.aborted) {
                return;
            }
            this.#updateZoomControls();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (context.signal?.aborted || isAbortError(runtimeError)) {
                return;
            }
            this.#handleTerminalInitializeError(runtimeError);
        }
        this.#ptyView?.focus();
    }

    bindPageEvents(): void {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Terminal UI missing');
        }
        const signal = this.pageLifecycle.beginListeners();
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'TerminalPage',
            isAction: isTerminalActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: ({ action }): void => this.#handleClick(action)
                }
            }
        });
    }

    #handleClick(action: TerminalActionId): void {
        switch (action) {
            case TERMINAL_ACTION_CLEAR:
                this.#clearTerminal();
                return;
            case TERMINAL_ACTION_TEXT_INCREASE:
                this.#adjustFontSize(1);
                return;
            case TERMINAL_ACTION_TEXT_DECREASE:
                this.#adjustFontSize(-1);
                return;
            case TERMINAL_ACTION_FOCUS:
                this.#ptyView?.focus();
                return;
        }
    }

    #clearTerminal(): void {
        this.#ptyView?.clear();
    }

    #adjustFontSize(delta: number): void {
        if (!this.#ptyView) return;
        const newSize = this.#ptyView.fontSize + delta;
        this.#ptyView.fontSize = newSize;
        this.#saveFontSize(this.#ptyView.fontSize);
        this.#updateZoomControls();
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#unregisterNavigationGuard();
        this.#detachActionController?.dispose();
        this.#detachActionController = null;
        this.#ptyView?.dispose();
        this.#ptyView = null;
        this.#ui = null;
    }

    #insertIcons(): void {
        this.services.applyIconMap(ACTION_ICONS);
    }

    #updateZoomControls(): void {
        const fontSize = this.#ptyView?.fontSize ?? TERMINAL_FONT_SIZE.DEFAULT;
        const root = this.#ui?.root ?? null;
        if (!root) {
            throw new Error('Terminal UI missing');
        }
        const decreaseButton = this.pageDom.requireHTMLElement('#terminal-text-decrease', root);
        const increaseButton = this.pageDom.requireHTMLElement('#terminal-text-increase', root);

        if (!(decreaseButton instanceof HTMLButtonElement)) {
            throw new TypeError('Terminal decrease button must be a button element');
        }
        if (!(increaseButton instanceof HTMLButtonElement)) {
            throw new TypeError('Terminal increase button must be a button element');
        }
        const disableDecrease = fontSize <= TERMINAL_FONT_SIZE.MIN;
        const disableIncrease = fontSize >= TERMINAL_FONT_SIZE.MAX;

        this.pageDom.updateProperty(decreaseButton, 'disabled', disableDecrease);
        this.pageDom.updateAttribute(decreaseButton, 'aria-disabled', disableDecrease ? 'true' : 'false');

        this.pageDom.updateProperty(increaseButton, 'disabled', disableIncrease);
        this.pageDom.updateAttribute(increaseButton, 'aria-disabled', disableIncrease ? 'true' : 'false');
    }
}

export { TerminalPage };
