/* SoAI - SoAI Connect settings lifecycle, QR rendering and actions [frontend/assets/ts/pages/settings/controllers/ConnectManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveInlineArrowStep } from '@core/layout/direction.ts';
import type { ConnectPairingResponse } from '@core/api/contracts/systemConnectPairingContracts.ts';
import { optionalNonNegativeIntegerDataAttribute } from '@core/dom/attributes.ts';
import { dom, optionalButton } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { ElementResizeRedrawWatcher } from '@core/layout/elementResizeRedraw.ts';
import { renderQrCanvas } from '@core/qr/qrCanvasRenderer.ts';
import { encodeQrByteModeM, type QrMatrix } from '@core/qr/qrEncoder.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { beginLoadingButton, clearLoadingButtonIfNeeded } from '@core/ui/loadingbuttons/service.ts';
import { copyTextWithBrowserClipboardFeedback } from '@core/ui/notifications/clipboardCopy.ts';
import { createSettingsCapabilityAvailability, markSettingsCapabilityFailed, markSettingsCapabilityReady, SettingsSectionLifecycle } from '@features/settings/public.ts';
import type { ConnectManagerHost } from '@pages/settings/contracts/connectManager.ts';
import { resolveConnectCandidates, type ConnectCandidate } from '@pages/settings/controllers/connect/mappers.ts';
import { renderConnectSettings } from '@pages/settings/controllers/connect/view.ts';

type ConnectReloadOutcome = 'loaded' | 'failed' | 'superseded';

const ADDRESS_NAVIGATION_KEYS: ReadonlySet<string> = new Set(['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End']);

const resolveNavigatedIndex = (key: string, currentIndex: number, count: number, element: Element): number => {
    if (key === 'Home') return 0;
    if (key === 'End') return count - 1;
    const inlineStep = resolveInlineArrowStep(key, element);
    const step = inlineStep !== 0 ? inlineStep : key === 'ArrowDown' ? 1 : -1;
    return (currentIndex + step + count) % count;
};

class ConnectManager {
    readonly #host: ConnectManagerHost;
    readonly #lifecycle = new SettingsSectionLifecycle();
    readonly #resizeRedraw = new ElementResizeRedrawWatcher();
    #pairing: ConnectPairingResponse | null = null;
    #candidates: readonly ConnectCandidate[] = [];
    #availability = createSettingsCapabilityAvailability();
    #selectedHost: string | null = null;
    #encoded: { readonly payload: string; readonly matrix: QrMatrix } | null = null;
    #reloadInFlight = false;

    constructor(host: ConnectManagerHost) {
        this.#host = host;
    }

    render(): TrustedHtml {
        return renderConnectSettings({ pairing: this.#pairing, availability: this.#availability, candidates: this.#candidates, selectedIndex: this.#selectedIndex() });
    }

    setupEventListeners(): void {
        const resumeReload = this.#reloadInFlight;
        this.dispose();
        this.#lifecycle.mount();
        this.#bind();
        this.#drawQr();
        if (resumeReload) this.#start(this.reload(), 'resumed reload');
    }

    async reload(): Promise<boolean> {
        return (await this.#load()) === 'loaded';
    }

    dispose(): void {
        this.#lifecycle.dispose('connect-dispose');
        this.#resizeRedraw.disconnect();
    }

    async #load(): Promise<ConnectReloadOutcome> {
        const run = this.#lifecycle.beginReload('connect-reload');
        if (run === null) return 'superseded';
        this.#reloadInFlight = true;
        try {
            const pairing = await this.#host.pairing.load({ signal: run.signal });
            if (!this.#lifecycle.isReloadCurrent(run)) return 'superseded';
            this.#reloadInFlight = false;
            this.#pairing = pairing;
            this.#candidates = resolveConnectCandidates(pairing, this.#host.page.readBrowserOrigin());
            if (!this.#candidates.some((candidate) => candidate.host === this.#selectedHost)) this.#selectedHost = this.#candidates[0]?.host ?? null;
            this.#availability = markSettingsCapabilityReady();
            this.#rerender();
            return 'loaded';
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(run)) return 'superseded';
            this.#reloadInFlight = false;
            errorHandler.warn('ConnectManager', 'SoAI Connect pairing details reload failed', ensureError(error));
            this.#availability = markSettingsCapabilityFailed(this.#availability);
            this.#rerender();
            return 'failed';
        }
    }

    #selectedIndex(): number {
        return Math.max(
            0,
            this.#candidates.findIndex((candidate) => candidate.host === this.#selectedHost)
        );
    }

    #bind(): void {
        this.#lifecycle.replaceCleanupGroup(
            'connect-actions',
            () => {
                const container = this.#host.view.requireContainer();
                const cleanups = [this.#host.view.bindEvent(container, 'click', (event) => this.#handleClick(event)), this.#host.view.bindEvent(container, 'keydown', (event) => this.#handleKeydown(event))];
                const windowRef = container.ownerDocument.defaultView;
                if (windowRef !== null) cleanups.push(this.#host.view.bindEvent(windowRef, 'resize', () => this.#drawQr()));
                return cleanups;
            },
            'SoAI Connect settings listener cleanup failed'
        );
    }

    #rerender(): void {
        if (!this.#lifecycle.isMounted) return;
        renderSettingsSection({
            container: this.#host.view.requireContainer(),
            render: () => this.render(),
            renderMarkup: (container, markup) => this.#host.view.updateHtml(container, markup),
            afterRender: () => this.#drawQr(),
            bind: () => this.#bind(),
            filter: () => this.#host.view.filter(),
            hasSearchQuery: () => this.#host.view.hasSearchQuery()
        });
    }

    #drawQr(): void {
        const candidate = this.#candidates[this.#selectedIndex()];
        const canvas = this.#lifecycle.isMounted ? dom.resolve('canvas.settings-connect__qr', this.#host.view.requireContainer()) : null;
        if (candidate === undefined || !(canvas instanceof HTMLCanvasElement)) {
            this.#resizeRedraw.disconnect();
            return;
        }
        if (this.#encoded?.payload !== candidate.payload) this.#encoded = { payload: candidate.payload, matrix: encodeQrByteModeM(new TextEncoder().encode(candidate.payload)) };
        const matrix = this.#encoded.matrix;
        const redraw = (): void => {
            renderQrCanvas(canvas, matrix);
        };
        redraw();
        this.#resizeRedraw.observe(canvas, redraw);
    }

    #handleClick(event: Event): void {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const button = optionalButton(target.closest('button[data-action]'), 'SoAI Connect action button');
        if (button === null) return;
        if (button.dataset.action === 'connect-refresh') this.#start(this.#refresh(button), 'refresh');
        if (button.dataset.action === 'connect-copy-address') this.#start(this.#copyAddress(button), 'address copy');
        if (button.dataset.action === 'connect-select-address') this.#select(optionalNonNegativeIntegerDataAttribute(button, 'addressIndex', 'SoAI Connect address chip'));
    }

    #handleKeydown(event: Event): void {
        if (!(event instanceof KeyboardEvent) || !ADDRESS_NAVIGATION_KEYS.has(event.key) || event.altKey || event.ctrlKey || event.metaKey) return;
        const target = event.target;
        if (!(target instanceof Element) || target.closest('[data-action="connect-select-address"]') === null || this.#candidates.length < 2) return;
        event.preventDefault();
        this.#select(resolveNavigatedIndex(event.key, this.#selectedIndex(), this.#candidates.length, this.#host.view.requireContainer()));
    }

    #select(index: number | null): void {
        const candidate = index === null ? undefined : this.#candidates[index];
        if (candidate === undefined) return;
        if (candidate.host !== this.#selectedHost) {
            this.#selectedHost = candidate.host;
            this.#rerender();
        }
        optionalButton(dom.resolve(`[data-action="connect-select-address"][data-address-index="${index}"]`, this.#host.view.requireContainer()), 'SoAI Connect address chip')?.focus();
    }

    async #refresh(button: HTMLButtonElement): Promise<void> {
        beginLoadingButton(button);
        try {
            if ((await this.#load()) === 'failed') this.#host.page.notify(i18n.t('settings.connect.loadFailed'), 'error');
        } finally {
            clearLoadingButtonIfNeeded(button);
        }
    }

    async #copyAddress(button: HTMLButtonElement): Promise<void> {
        const candidate = this.#candidates[this.#selectedIndex()];
        if (candidate === undefined) return;
        await copyTextWithBrowserClipboardFeedback({ showNotification: (message, type, duration) => this.#host.page.notify(message, type, duration) }, { text: candidate.url, successMessage: i18n.t('settings.connect.addressCopied'), blurElement: button });
    }

    #start(operation: Promise<boolean | void>, context: string): void {
        void operation.catch((error) => {
            errorHandler.error('ConnectManager', `SoAI Connect ${context} failed outside its action boundary`, ensureError(error));
        });
    }
}

export { ConnectManager };
