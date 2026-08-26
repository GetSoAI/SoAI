/* SoAI - Overlays feature power action [frontend/assets/ts/features/overlays/PowerAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { dom } from '@core/dom/dom.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { requireDocument } from '@core/environment/public.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setIconSlot } from '@core/ui/icons/view.ts';
import { ACTION_CONFIG, isPowerActionKey } from '@features/overlays/powerActionConfig.ts';
import { PowerActionRecoveryMonitor } from '@features/overlays/powerActionRecoveryMonitor.ts';

const POWER_ACTION_OVERLAY_SERVICE_ID = 'features.overlays.power';

interface MaintenanceCoordinator {
    activate: (reason: string, options?: { mode?: 'hold' | 'observe' }) => symbol;
    deactivate: (token: symbol) => void;
}

interface PowerActionOverlayElements {
    overlay: HTMLElement;
    title: HTMLElement;
    description: HTMLElement;
    statusIcon: HTMLElement;
}

interface PowerActionOverlayDependencies {
    api: ApiClient;
    maintenanceCoordinator: MaintenanceCoordinator;
}

const requireHTMLElement = (selector: string): HTMLElement => {
    const doc = requireDocument();
    const element = dom.resolve(selector, doc);
    if (!element) {
        throw new Error(`PowerActionOverlay: missing required element ${selector}`);
    }
    return narrowHTMLElement(element, `PowerActionOverlay ${selector}`);
};

class PowerActionOverlay {
    readonly #maintenance: MaintenanceCoordinator;
    readonly #recoveryMonitor: PowerActionRecoveryMonitor;

    #initialized = false;
    #elements: PowerActionOverlayElements | null = null;
    #currentVariantClass: string | null = null;
    #offlineMessage: string | null = null;
    #maintenanceToken: symbol | null = null;
    #abortController: AbortController | null = null;

    constructor(dependencies: PowerActionOverlayDependencies) {
        if (!dependencies || !isObject(dependencies)) {
            throw new Error('PowerActionOverlay requires deps');
        }
        if (!isObject(dependencies.api)) {
            throw new Error('PowerActionOverlay requires api');
        }
        if (!isObject(dependencies.maintenanceCoordinator)) {
            throw new Error('PowerActionOverlay requires maintenanceCoordinator');
        }
        if (!isFunction(dependencies.maintenanceCoordinator.activate) || !isFunction(dependencies.maintenanceCoordinator.deactivate)) {
            throw new Error('PowerActionOverlay maintenanceCoordinator is invalid');
        }
        this.#maintenance = dependencies.maintenanceCoordinator;
        this.#recoveryMonitor = new PowerActionRecoveryMonitor(dependencies.api, {
            canPoll: () => requireDocument().visibilityState !== 'hidden',
            onInterrupted: () => this.#showOfflineState(),
            onRecovered: () => this.#completeRecovery()
        });
    }

    initialize(): void {
        if (this.#initialized) return;
        this.#elements = {
            overlay: requireHTMLElement('#power-action-overlay'),
            title: requireHTMLElement('#power-overlay-title'),
            description: requireHTMLElement('#power-overlay-description'),
            statusIcon: requireHTMLElement('#power-overlay-status-icon')
        };
        const doc = requireDocument();
        this.#abortController = new AbortController();
        doc.addEventListener(
            'visibilitychange',
            () => {
                if (doc.visibilityState === 'hidden') {
                    this.#recoveryMonitor.suspendPolling();
                    return;
                }
                if (doc.visibilityState === 'visible') {
                    this.#recoveryMonitor.resumePolling();
                }
            },
            { signal: this.#abortController.signal }
        );
        this.#initialized = true;
    }

    destroy(): void {
        this.#recoveryMonitor.stop();
        this.#hideOverlay();
        this.#abortController?.abort();
        this.#abortController = null;
        this.#elements = null;
        this.#initialized = false;
        this.#offlineMessage = null;
    }

    show(actionKey: string): void {
        if (!isPowerActionKey(actionKey)) {
            throw new Error(`PowerActionOverlay: unsupported action '${actionKey}'`);
        }
        this.initialize();
        const elements = this.#elements;
        if (!elements) {
            throw new Error('PowerActionOverlay: elements are not initialized');
        }

        const config = ACTION_CONFIG[actionKey];
        this.#activateMaintenance(actionKey);

        const message = config.getTitle();
        const monitoringMessage = config.getMonitoring();

        elements.title.textContent = message;
        elements.description.textContent = monitoringMessage;
        setIconSlot(elements.statusIcon, getIconSync(config.statusIcon, { size: 68, strokeWidth: 1.5 }), { className: elements.statusIcon.className });

        if (this.#currentVariantClass) {
            elements.overlay.classList.remove(this.#currentVariantClass);
            this.#currentVariantClass = null;
        }
        if (config.overlayClass) {
            elements.overlay.classList.add(config.overlayClass);
            this.#currentVariantClass = config.overlayClass;
        }

        elements.overlay.classList.remove('u-hidden');
        elements.overlay.classList.add('is-visible');

        this.#offlineMessage = config.getOffline();
        this.#recoveryMonitor.start(actionKey);
    }

    hide(): void {
        this.#completeRecovery();
    }

    #completeRecovery(): void {
        this.#recoveryMonitor.stop();
        this.#hideOverlay();
    }

    #hideOverlay(): void {
        this.#releaseMaintenance();
        const elements = this.#elements;
        if (!elements) return;

        elements.overlay.classList.remove('is-visible');
        elements.overlay.classList.add('u-hidden');

        if (this.#currentVariantClass) {
            elements.overlay.classList.remove(this.#currentVariantClass);
            this.#currentVariantClass = null;
        }
        this.#offlineMessage = null;
    }

    #showOfflineState(): void {
        const elements = this.#elements;
        if (elements && this.#offlineMessage) elements.description.textContent = this.#offlineMessage;
    }

    #activateMaintenance(reason: string): void {
        this.#releaseMaintenance();
        this.#maintenanceToken = this.#maintenance.activate(reason, { mode: 'observe' });
    }

    #releaseMaintenance(): void {
        const token = this.#maintenanceToken;
        if (!token) return;
        this.#maintenance.deactivate(token);
        this.#maintenanceToken = null;
    }
}

const createPowerActionOverlay = (dependencies: PowerActionOverlayDependencies): PowerActionOverlay => new PowerActionOverlay(dependencies);

export { POWER_ACTION_OVERLAY_SERVICE_ID, PowerActionOverlay, createPowerActionOverlay };
