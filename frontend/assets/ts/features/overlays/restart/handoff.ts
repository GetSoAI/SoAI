/* SoAI - Restart overlay HTTP/HTTPS address handoff guidance [frontend/assets/ts/features/overlays/restart/handoff.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { copyText } from '@core/clipboard.ts';
import { resolveConnectionHandoff, type ConnectionHandoff } from '@core/connectionHandoff.ts';
import { dom } from '@core/dom/dom.ts';
import { getLocation } from '@core/environment/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { i18n } from '@core/i18n/index.ts';
import type { RestartState } from '@core/restartStateGateway.ts';
import { subscribeRestartState } from '@core/restartStateService.ts';
import type { OperationType } from '@features/overlays/restart/types.ts';

const HANDOFF_OPERATION_TYPES: ReadonlySet<OperationType> = new Set(['restart-application', 'system-reboot', 'update-soai', 'connection-lost']);

interface RestartHandoffHost {
    resolveContent(): HTMLElement | null;
    resolveApiBaseUrl(): string | null;
    updateText(element: HTMLElement, value: string): void;
}

const describeHandoff = (handoff: ConnectionHandoff, interrupted: boolean): string => {
    if (handoff.type === 'manual') return handoff.requestedScheme === 'https' ? i18n.t('restartOverlay.handoff.manualHttps') : i18n.t('restartOverlay.handoff.manualHttp');
    return interrupted ? i18n.t('restartOverlay.handoff.newAddress') : i18n.t('restartOverlay.handoff.plannedAddress');
};

class RestartHandoffController {
    readonly #host: RestartHandoffHost;
    readonly #resources = new ResourceTracker();
    #unsubscribe: (() => void) | null = null;
    #container: HTMLElement | null = null;
    #handoff: ConnectionHandoff | null = null;
    #interrupted = false;
    #signature: string | null = null;

    constructor(host: RestartHandoffHost) {
        this.#host = host;
    }

    start(type: OperationType, interrupted: boolean): void {
        this.stop();
        if (!HANDOFF_OPERATION_TYPES.has(type)) return;
        this.#interrupted = interrupted || type === 'connection-lost';
        this.#unsubscribe = subscribeRestartState((state) => this.#apply(state));
    }

    markInterrupted(): void {
        if (this.#interrupted || this.#unsubscribe === null) return;
        this.#interrupted = true;
        this.#render();
    }

    stop(): void {
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#handoff = null;
        this.#interrupted = false;
        this.#render();
    }

    #apply(state: RestartState): void {
        this.#handoff = resolveConnectionHandoff(state.connectionTransition, getLocation().href, this.#host.resolveApiBaseUrl());
        this.#render();
    }

    #render(): void {
        const handoff = this.#handoff;
        const signature = handoff === null ? null : JSON.stringify([handoff, this.#interrupted]);
        if (signature === this.#signature) return;
        this.#signature = signature;
        this.#resources.cleanup();
        if (this.#container !== null) dom.remove(this.#container);
        this.#container = null;
        const content = this.#host.resolveContent();
        if (handoff === null || content === null) return;
        const container = dom.create('div', { className: 'restart-handoff', role: 'status' });
        const message = dom.create('p', { className: 'restart-handoff-message' });
        this.#host.updateText(message, describeHandoff(handoff, this.#interrupted));
        dom.appendChild(container, message);
        if (handoff.type === 'address') dom.appendChild(container, this.#createAddressActions(handoff.url));
        dom.appendChild(content, container);
        this.#container = container;
    }

    #createAddressActions(url: string): DocumentFragment {
        const fragment = dom.createFragment();
        const address = dom.create('code', { className: 'restart-handoff-address' });
        this.#host.updateText(address, url);
        const actions = dom.create('div', { className: 'restart-handoff-actions' });
        const open = dom.create('a', { className: 'ui-button ui-variant-accent', href: url, target: '_blank', rel: 'noopener noreferrer' });
        this.#host.updateText(open, i18n.t('restartOverlay.handoff.open'));
        const copy = dom.create('button', { className: 'ui-button', type: 'button' });
        this.#host.updateText(copy, i18n.t('restartOverlay.handoff.copy'));
        this.#resources.addEventListener(copy, 'click', () => {
            terminateHandledPromise(copyText(url, { successMessage: i18n.t('restartOverlay.handoff.copied') }));
        });
        dom.appendChild(actions, [open, copy]);
        dom.appendChild(fragment, [address, actions]);
        return fragment;
    }
}

export { RestartHandoffController };
export type { RestartHandoffHost };
