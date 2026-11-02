/* SoAI - Chat preference pending-journal storage ownership [frontend/assets/ts/core/storage/chatpreferences/ChatPreferenceJournalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { decodeChatPreferencePendingJournal, journalStorageKey, serializeChatPreferencePendingJournal, type ChatPreferencePendingJournal } from '@core/storage/chatpreferences/chatPreferencePendingJournal.ts';
import { preferenceRequestIdentityMatchesSession, readPreferenceRequestIdentity, type PreferenceRequestIdentity } from '@core/storage/chatpreferences/preferenceRequestIdentity.ts';
import type { StorageAdapters, StorageRuntimeState } from '@core/storage/service/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

class ChatPreferenceJournalController {
    readonly #adapters: StorageAdapters;
    readonly #state: StorageRuntimeState;
    #warningReported = false;

    constructor(adapters: StorageAdapters, state: StorageRuntimeState) {
        this.#adapters = adapters;
        this.#state = state;
    }

    read(identity: PreferenceRequestIdentity): ChatPreferencePendingJournal | null {
        if (!preferenceRequestIdentityMatchesSession(this.#state, identity)) return null;
        const key = journalStorageKey(identity.userId);
        let value: JsonValue | null | undefined;
        try {
            value = this.#adapters.readStorage('sessionStorage', key);
        } catch (error) {
            this.#reportWarning(ensureError(error));
            value = null;
        }
        if (value === null || value === undefined) return null;
        const journal = decodeChatPreferencePendingJournal(value, identity.userId, identity.windowId);
        if (journal) return journal;
        try {
            this.#adapters.writeStorage('sessionStorage', key, null);
        } catch (error) {
            this.#reportWarning(ensureError(error));
        }
        this.#reportWarning(new Error('Invalid chat preference pending journal.'));
        return null;
    }

    writeForCurrentIdentity(identity: PreferenceRequestIdentity | null, chatDelta: JsonObject, conversationDefaultsDelta: JsonObject): void {
        if (identity) {
            this.write(identity, chatDelta, conversationDefaultsDelta);
            return;
        }
        const current = readPreferenceRequestIdentity(this.#state);
        if (current) this.write(current, chatDelta, conversationDefaultsDelta);
    }

    write(identity: PreferenceRequestIdentity, chatDelta: JsonObject, conversationDefaultsDelta: JsonObject): void {
        if (!preferenceRequestIdentityMatchesSession(this.#state, identity)) return;
        const key = journalStorageKey(identity.userId);
        try {
            if (Object.keys(chatDelta).length === 0 && Object.keys(conversationDefaultsDelta).length === 0) {
                this.#adapters.writeStorage('sessionStorage', key, null);
                return;
            }
            this.#adapters.writeStorage('sessionStorage', key, serializeChatPreferencePendingJournal({ version: 1, userId: identity.userId, windowId: identity.windowId, chatDelta, conversationDefaultsDelta }));
        } catch (error) {
            this.#reportWarning(ensureError(error));
        }
    }

    #reportWarning(error: Error): void {
        if (this.#warningReported) return;
        this.#warningReported = true;
        errorHandler.warn('StorageManager', 'Chat preference reload durability is degraded', error);
    }
}

export { ChatPreferenceJournalController };
