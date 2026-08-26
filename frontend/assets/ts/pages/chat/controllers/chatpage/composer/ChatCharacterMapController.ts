/* SoAI - Character map page-lifetime session ownership [frontend/assets/ts/pages/chat/controllers/chatpage/composer/ChatCharacterMapController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { resolveAssetPath } from '@core/assetPaths.ts';
import { AsyncOnceGuard } from '@core/concurrency/AsyncOnce.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';
import { CHAT_CHARACTER_MAP_MODAL_ID, decodeCharacterMapCatalog, type CharacterMapCatalog } from '@features/chat/public.ts';
import { ChatCharacterMapModalController } from '@pages/chat/controllers/modals/charactermap/ChatCharacterMapModalController.ts';
import { readCharacterMapViewState, writeCharacterMapViewState, type CharacterMapViewStateStorage } from '@pages/chat/controllers/modals/charactermap/state.ts';
import type { ChatComposerController } from '@pages/chat/controllers/chatpage/composer/ChatComposerController.ts';

interface ChatCharacterMapControllerHost {
    api: Pick<ApiClient, 'fetchAsset'>;
    composer: Pick<ChatComposerController, 'insertTextAtCaret'>;
    feedback: Pick<PageFeedback, 'handle' | 'show'>;
    services: Pick<PageServices, 'hasClipboardSupport' | 'copyToClipboard'>;
    storage: CharacterMapViewStateStorage;
    requirePresenter(): ModalPresenterApi;
    getLifecycleSignal(): AbortSignal | null;
    runTask(operationId: string, task: () => Promise<void> | void): void;
}

class ChatCharacterMapController {
    readonly #host: ChatCharacterMapControllerHost;
    readonly #catalogGuard = new AsyncOnceGuard<CharacterMapCatalog>();
    #controller: ChatCharacterMapModalController | null = null;
    #generation = 0;
    #disposed = false;

    constructor(host: ChatCharacterMapControllerHost) {
        this.#host = host;
    }

    open(): void {
        if (this.#disposed) throw new Error('Character-map controller is disposed');
        const presenter = this.#host.requirePresenter();
        const generation = ++this.#generation;
        this.#host.runTask(`chat:openCharacterMap:${generation}`, async () => {
            try {
                await runModalSession({
                    presenter,
                    modalId: CHAT_CHARACTER_MAP_MODAL_ID,
                    onAlreadyOpen: 'replace',
                    initialResult: undefined,
                    initialize: ({ modal, signal }) => {
                        const controller = new ChatCharacterMapModalController(
                            {
                                feedback: this.#host.feedback,
                                initialViewState: readCharacterMapViewState(this.#host.storage),
                                loadCatalog: () => this.#loadCatalog(),
                                saveViewState: (state) => writeCharacterMapViewState(this.#host.storage, state),
                                insertText: (text) => this.#host.composer.insertTextAtCaret(text, 'inline'),
                                closeAfterInsert: () => presenter.close(CHAT_CHARACTER_MAP_MODAL_ID, { restoreFocus: false, reason: 'insert' }),
                                hasClipboardSupport: () => this.#host.services.hasClipboardSupport(),
                                copyToClipboard: (text, options) => this.#host.services.copyToClipboard(text, options),
                                runTask: (operationId, task) => this.#host.runTask(operationId, task)
                            },
                            modal,
                            signal
                        );
                        this.#controller = controller;
                        return { dispose: () => controller.dispose() };
                    }
                });
            } finally {
                if (generation === this.#generation) this.#controller = null;
            }
        });
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#generation += 1;
        const presenter = this.#host.requirePresenter();
        const isOpen = presenter.isOpen(CHAT_CHARACTER_MAP_MODAL_ID);
        if (isOpen) {
            presenter.close(CHAT_CHARACTER_MAP_MODAL_ID, { force: true, restoreFocus: false, reason: 'page-dispose' });
        } else {
            this.#controller?.dispose();
        }
        this.#controller = null;
        this.#catalogGuard.dispose();
    }

    #loadCatalog(): Promise<CharacterMapCatalog> {
        return this.#catalogGuard.run(async () => {
            const signal = this.#host.getLifecycleSignal();
            if (signal === null) throw new Error('Character-map load requires an active page lifecycle signal');
            throwIfAborted(signal);
            const payload = await this.#host.api.fetchAsset(resolveAssetPath('unicode/character-map.json'), { responseType: 'json', signal, timeout: 30_000 });
            if (!isJsonValue(payload)) throw new Error('Character-map catalog response is not JSON');
            return decodeCharacterMapCatalog(payload);
        });
    }
}

export { ChatCharacterMapController };
export type { ChatCharacterMapControllerHost };
