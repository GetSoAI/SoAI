/* SoAI - Chat configuration aggregate save outcome presentation [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatConfigurationSaveOutcomeDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveHandledOperationCause } from '@core/operationErrorNotifier.ts';
import { i18n } from '@core/i18n/index.ts';

type ChatConfigurationSaveUnitId = 'conversation' | 'knowledge' | 'skills' | 'tools' | 'preferences';
type ChatConfigurationSaveTerminalOutcome = 'saved' | 'degraded' | 'stopped';
type ChatConfigurationSavePresentation = Readonly<{ message: string; type: 'error' | 'success' | 'warning' }>;

const translateOwner = (unitId: ChatConfigurationSaveUnitId): string => {
    if (unitId === 'conversation') return i18n.t('chat.configuration.saveOwners.conversation');
    if (unitId === 'knowledge') return i18n.t('chat.configuration.saveOwners.knowledge');
    if (unitId === 'skills') return i18n.t('chat.configuration.skills.title');
    if (unitId === 'tools') return i18n.t('chat.configuration.saveOwners.tools');
    return i18n.t('chat.configuration.saveOwners.preferences');
};

class ChatConfigurationSaveOutcomeTracker {
    #completed: ChatConfigurationSaveUnitId[] = [];
    #failed: ChatConfigurationSaveUnitId | null = null;
    #failureCause: string | null = null;
    #session: WeakKey | null = null;

    begin(session: WeakKey | null): void {
        this.#completed = [];
        this.#failed = null;
        this.#failureCause = null;
        this.#session = session;
    }

    isCurrent(session: WeakKey | null): boolean {
        return this.#session !== null && this.#session === session;
    }

    complete(unitId: ChatConfigurationSaveUnitId): void {
        if (!this.#completed.includes(unitId)) this.#completed.push(unitId);
    }

    fail(unitId: ChatConfigurationSaveUnitId, cause: Error | null = null): void {
        this.#failed = unitId;
        this.#failureCause = cause === null ? null : resolveHandledOperationCause(cause);
    }

    presentation(outcome: ChatConfigurationSaveTerminalOutcome): ChatConfigurationSavePresentation | null {
        if (outcome === 'saved') return { message: i18n.t('chat.configuration.saved'), type: 'success' };
        const completed = this.#completed.map(translateOwner).join(', ');
        if (outcome === 'degraded') return { message: i18n.t('chat.configuration.saveDegradedDetail', { completed }), type: 'warning' };
        if (!this.#failed) return null;
        const message = i18n.t('chat.configuration.savePartial', { completed: completed || i18n.t('common.none'), failed: translateOwner(this.#failed) });
        return { message: this.#failureCause ? `${message} ${this.#failureCause}` : message, type: 'error' };
    }
}

export { ChatConfigurationSaveOutcomeTracker };
export type { ChatConfigurationSaveUnitId };
