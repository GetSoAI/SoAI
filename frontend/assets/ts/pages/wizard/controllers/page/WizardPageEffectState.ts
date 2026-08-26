/* SoAI - Wizard status, visibility, and effect service ownership [frontend/assets/ts/pages/wizard/controllers/page/WizardPageEffectState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WizardStatus } from '@core/auth/public.ts';
import type { WizardPageEffectsHost } from '@pages/wizard/controllers/page/types.ts';

type WizardEffectAuth = NonNullable<ReturnType<WizardPageEffectsHost['getAuth']>> & { isAuthenticated: boolean };

class WizardPageEffectState implements WizardPageEffectsHost {
    readonly #auth: WizardEffectAuth;
    readonly #storage: NonNullable<ReturnType<WizardPageEffectsHost['getStorage']>>;
    readonly #logWarning: (message: string, error?: Error) => void;
    status: WizardStatus | null = null;
    visible: boolean | null = null;

    constructor(auth: WizardEffectAuth, storage: NonNullable<ReturnType<WizardPageEffectsHost['getStorage']>>, logWarning: (message: string, error?: Error) => void) {
        this.#auth = auth;
        this.#storage = storage;
        this.#logWarning = logWarning;
    }

    getAuth(): WizardEffectAuth {
        return this.#auth;
    }

    getStorage(): NonNullable<ReturnType<WizardPageEffectsHost['getStorage']>> {
        return this.#storage;
    }

    isAuthenticated(): boolean {
        return this.#auth.isAuthenticated === true;
    }

    getWizardStatus(): WizardStatus | null {
        return this.status;
    }

    setWizardStatus(status: WizardStatus | null): void {
        this.status = status;
    }

    getWizardVisible(): boolean | null {
        return this.visible;
    }

    setWizardVisible(visible: boolean | null): void {
        this.visible = visible;
    }

    logWarn(message: string, error?: Error): void {
        this.#logWarning(message, error);
    }
}

export { WizardPageEffectState };
