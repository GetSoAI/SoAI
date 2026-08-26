/* SoAI - Shared layout licensing shortcut controller [frontend/assets/ts/core/layout/header/LicensingShortcutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager, type AuthManager } from '@core/auth/public.ts';
import { getApiClient } from '@core/api/service.ts';
import type { LicensingSettingsStatus } from '@core/api/contracts/licensingSettingsContracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { licensingStateNeedsAttention, licensingStateRequiresRepair } from '@core/licensing/licensingState.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { subscribeManagedWebSocketContract } from '@core/realtime/websocketBatchSubscription.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';

class LicensingShortcutController {
    #actionController: HeaderActionController | null = null;
    #authManager: AuthManager | null = null;
    #unsubscribeLogin: (() => void) | null = null;
    #unsubscribeLogout: (() => void) | null = null;
    #unsubscribeStatus: (() => void) | null = null;
    #abortController: AbortController | null = null;
    #refreshSequence = 0;

    readonly #navigate = (): void => {
        requireRouter().navigateWithQuery('settings', { tab: 'licensing' });
    };

    readonly #synchronize = (): void => {
        const actionController = this.#actionController;
        const authManager = this.#authManager;
        if (!actionController || !authManager) return;
        if (!authManager.getCurrentUser() || !authManager.isAdmin()) {
            this.#refreshSequence += 1;
            actionController.hide();
            return;
        }
        void this.#refresh().catch((error) => {
            errorHandler.warn('LicensingShortcutController', 'Licensing shortcut refresh scheduling failed', ensureError(error));
        });
    };

    #hasIssue(status: LicensingSettingsStatus): boolean {
        return status.requiresRepairPlane || licensingStateNeedsAttention(status.state) || licensingStateRequiresRepair(status.state);
    }

    async #refresh(): Promise<void> {
        const actionController = this.#actionController;
        const authManager = this.#authManager;
        const signal = this.#abortController?.signal;
        if (!actionController || !authManager || !signal || signal.aborted || !authManager.getCurrentUser() || !authManager.isAdmin()) return;
        const sequence = ++this.#refreshSequence;
        try {
            const status = await getApiClient().webui.licensing.status({ signal });
            if (signal.aborted || sequence !== this.#refreshSequence || !authManager.getCurrentUser() || !authManager.isAdmin()) return;
            if (this.#hasIssue(status)) {
                actionController.show({ onClick: this.#navigate });
                return;
            }
            actionController.hide();
        } catch (error) {
            if (signal.aborted || sequence !== this.#refreshSequence || isAbortError(error)) return;
            actionController.hide();
            errorHandler.warn('LicensingShortcutController', 'Licensing shortcut status refresh failed', ensureError(error));
        }
    }

    initialize(): void {
        this.destroy();
        this.#authManager = getAuthManager();
        this.#abortController = new AbortController();
        this.#actionController = createHeaderActionController({
            actionId: HEADER_ACTION_IDS.licensing,
            contextId: 'header-licensing-shortcut'
        });
        this.#unsubscribeLogin = this.#authManager.onLogin(this.#synchronize);
        this.#unsubscribeLogout = this.#authManager.onLogout(this.#synchronize);
        this.#unsubscribeStatus = subscribeManagedWebSocketContract({ label: 'LicensingShortcutController', contract: WEBSOCKET_EVENT_CONTRACTS.licensing.statusChanged, handler: this.#synchronize });
        this.#synchronize();
    }

    destroy(): void {
        this.#unsubscribeLogin?.();
        this.#unsubscribeLogout?.();
        this.#unsubscribeStatus?.();
        this.#abortController?.abort();
        this.#refreshSequence += 1;
        this.#unsubscribeLogin = null;
        this.#unsubscribeLogout = null;
        this.#unsubscribeStatus = null;
        this.#abortController = null;
        this.#actionController?.dispose();
        this.#actionController = null;
        this.#authManager = null;
    }
}

export { LicensingShortcutController };
