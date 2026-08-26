/* SoAI - Settings instance identity manager [frontend/assets/ts/pages/settings/controllers/instanceidentity/InstanceIdentityManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowInput } from '@core/dom/narrowElement.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { InstanceIdentityManagerDependencies, InstanceIdentityManagerHost } from '@pages/settings/controllers/instanceidentity/contracts.ts';
import { INSTANCE_NAME_FIELD_KEY, INSTANCE_NAME_INPUT_ID, INSTANCE_NAME_MAX_LENGTH, renderInstanceIdentity } from '@pages/settings/controllers/instanceidentity/view.ts';

const normalizeInstanceName = (value: string): string | null => value.trim() || null;

const hasInvalidInstanceNameCharacters = (value: string): boolean =>
    Array.from(value).some((character) => {
        const codePoint = character.codePointAt(0);
        return codePoint !== undefined && (codePoint < 32 || codePoint === 127);
    });

class InstanceIdentityManager {
    readonly #host: InstanceIdentityManagerHost;
    readonly #instanceId: string;
    #originalName: string | null;
    #currentName: string | null;
    #disposer: (() => void) | null = null;

    constructor({ host, instanceId, instanceName }: InstanceIdentityManagerDependencies) {
        this.#host = host;
        this.#instanceId = instanceId;
        this.#originalName = instanceName;
        this.#currentName = instanceName;
    }

    render(): TrustedHtml {
        return renderInstanceIdentity(this.#instanceId, this.#currentName);
    }

    setupEventListeners(): void {
        this.dispose();
        const candidate = this.#host.pageDom.optional(INSTANCE_NAME_INPUT_ID);
        if (!candidate) {
            throw new Error('Instance name input is required for administrators');
        }
        const input = narrowInput(candidate, 'Instance name input');
        this.#disposer = this.#host.pageResources.on(input, 'input', () => {
            this.#currentName = normalizeInstanceName(input.value);
            const valid = this.isValid();
            this.#host.syncManualDirtyField(INSTANCE_NAME_FIELD_KEY, this.hasChanges(), valid);
            this.#host.notifySaveChanged();
        });
        this.#syncDirtyState();
    }

    hasChanges(): boolean {
        return this.#currentName !== this.#originalName;
    }

    isValid(): boolean {
        const value = this.#currentName ?? '';
        return Array.from(value).length <= INSTANCE_NAME_MAX_LENGTH && !hasInvalidInstanceNameCharacters(value);
    }

    async save(): Promise<void> {
        if (!this.hasChanges()) {
            return;
        }
        if (!this.isValid()) {
            throw new Error('Instance name exceeds the maximum length');
        }
        const savedName = await this.#host.updateInstanceName(this.#currentName);
        this.#originalName = savedName;
        this.#currentName = savedName;
        const candidate = this.#host.pageDom.optional(INSTANCE_NAME_INPUT_ID);
        if (candidate) {
            const input = narrowInput(candidate, 'Instance name input');
            this.#host.pageDom.updateProperty(input, 'value', savedName ?? '');
        }
        this.#host.clearManualDirtyField(INSTANCE_NAME_FIELD_KEY);
    }

    dispose(): void {
        this.#disposer?.();
        this.#disposer = null;
    }

    #syncDirtyState(): void {
        this.#host.syncManualDirtyField(INSTANCE_NAME_FIELD_KEY, this.hasChanges(), this.isValid());
    }
}

export { InstanceIdentityManager, hasInvalidInstanceNameCharacters, normalizeInstanceName };
