/* SoAI - Skill settings snapshots and bounded WebSocket recovery [frontend/assets/ts/features/chat/conversationsettings/skills/resources.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeSkillLibrary, decodeSkillSelection } from '@core/api/contracts/webuiSkillContracts.ts';
import type { SkillLibrary, SkillSelection } from '@core/api/contracts/webuiSkillContractTypes.ts';
import { ResourceReconciler } from '@core/realtime/streammanager/resources/resourceReconciler.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { bindWindowReactivation } from '@core/dom/windowReactivation.ts';

interface SkillResourceObserver {
    library(value: SkillLibrary): void;
    selection(value: SkillSelection): void;
    status(library: ResourceReconciliationSnapshot, selection: ResourceReconciliationSnapshot | null): void;
}

class SkillSettingsResources {
    readonly #library = new ResourceReconciler('skills.library');
    readonly #selection = new ResourceReconciler('skills.selection');
    readonly #conversationId: string | null;
    readonly #observer: SkillResourceObserver;
    readonly #disposers: Array<() => void> = [];
    #libraryRevision = 0;
    #selectionRevision = 0;
    #disposed = false;

    constructor(conversationId: string | null, observer: SkillResourceObserver) {
        this.#conversationId = conversationId;
        this.#observer = observer;
    }

    async start(): Promise<void> {
        this.#disposers.push(bindWindowReactivation(() => terminateHandledPromise(this.refresh())));
        this.#library.setLiveDemand(true);
        this.#selection.setLiveDemand(this.#conversationId !== null);
        this.#disposers.push(
            this.#library.subscribe((snapshot) => {
                if (snapshot.status === 'ready') this.#observer.library(decodeSkillLibrary(snapshot.value));
                this.#emitStatus();
            })
        );
        this.#disposers.push(
            this.#selection.subscribe((snapshot) => {
                if (snapshot.status === 'ready') this.#observer.selection(decodeSkillSelection(snapshot.value));
                this.#emitStatus();
            })
        );
        this.#disposers.push(
            subscribeManagedWebSocketContracts({
                label: 'SkillSettingsResources',
                events: [
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.skills.libraryChanged,
                        handler: (event) => {
                            if (event.revision <= this.#libraryRevision) return;
                            this.#libraryRevision = event.revision;
                            this.#library.invalidate('skill-library-changed');
                        },
                        onInvalidPayload: (error) => this.#library.rejectPush(error)
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.skills.selectionChanged,
                        handler: (event) => {
                            if (event.conversationId !== this.#conversationId || event.revision <= this.#selectionRevision) return;
                            this.#selectionRevision = event.revision;
                            this.#selection.invalidate('skill-selection-changed');
                        },
                        onInvalidPayload: (error) => this.#selection.rejectPush(error)
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
                        handler: () => {
                            this.#library.disconnect();
                            this.#selection.disconnect();
                        }
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
                        handler: () => {
                            this.#library.replaceTransportEpoch(this.#library.snapshot.transportEpoch + 1);
                            this.#selection.replaceTransportEpoch(this.#selection.snapshot.transportEpoch + 1);
                            terminateHandledPromise(this.refresh());
                        }
                    })
                ]
            })
        );
        await this.refresh();
    }

    async refresh(): Promise<void> {
        if (this.#disposed) return;
        const operations = [
            this.#library.reconcile(
                async ({ signal }) => {
                    const payload = await requestWebSocketSnapshotPayload('skills.library', null, { signal });
                    const library = decodeSkillLibrary(payload);
                    if (library.revision < this.#libraryRevision) throw new Error('Skill library snapshot precedes its observed revision.');
                    this.#libraryRevision = library.revision;
                    return payload;
                },
                { force: true, source: 'websocket-snapshot' }
            )
        ];
        const conversationId = this.#conversationId;
        if (conversationId !== null)
            operations.push(
                this.#selection.reconcile(
                    async ({ signal }) => {
                        const payload = await requestWebSocketSnapshotPayload('skills.selection', { 'conv_id': conversationId }, { signal });
                        const selection = decodeSkillSelection(payload);
                        if (selection.conversationId !== conversationId || selection.revision < this.#selectionRevision) throw new Error('Skill selection snapshot differs from its observed identity.');
                        this.#selectionRevision = selection.revision;
                        return payload;
                    },
                    { force: true, source: 'websocket-snapshot' }
                )
            );
        await Promise.all(operations);
    }

    invalidateSelection(): void {
        this.#selection.invalidate('skill-save-unconfirmed');
    }

    acceptedSelection(selection: SkillSelection): void {
        if (selection.conversationId !== this.#conversationId) return;
        this.#selectionRevision = Math.max(this.#selectionRevision, selection.revision);
        this.#selection.invalidate('skill-save-accepted');
    }

    dispose(): void {
        this.#disposed = true;
        for (const dispose of this.#disposers.splice(0)) dispose();
        this.#library.dispose();
        this.#selection.dispose();
    }

    #emitStatus(): void {
        this.#observer.status(this.#library.snapshot, this.#conversationId === null ? null : this.#selection.snapshot);
    }
}

export { SkillSettingsResources };
export type { SkillResourceObserver };
