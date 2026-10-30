/* SoAI - Reusable attachment dialog session and action authority [frontend/assets/ts/features/attachmodal/AttachModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AsyncOnceGuard } from '@core/concurrency/AsyncOnce.ts';
import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { bindTypedResolvedDataActionListener } from '@core/dom/dataActionBinding.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { createAbortSignalScope, isAbortError, type AbortSignalScope } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runAsyncCleanupStepCollectingFailure, runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { LifecycleScope, type LifecycleRun } from '@core/lifecycle/lifecycleScope.ts';
import { bindManagedModalLifecycleEvents, createManagedModalCloseBinding } from '@core/modals/managedModalLifecycle.ts';
import { createBusyDisabledToken, setBusyDisabledState, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import type { TabsComponent } from '@core/ui/controls/Tabs.ts';
import { ATTACH_MODAL_ACTIONS, isAttachModalAction, type AttachModalAction } from '@features/attachmodal/actions.ts';
import { createCameraCaptureRuntime, type AttachCameraRuntime } from '@features/attachmodal/cameraCapture.ts';
import { ATTACH_MODAL_ID } from '@features/attachmodal/constants.ts';
import type { AttachModalConsumer, AttachModalContent, AttachModalOpenOptions, AttachModalTab } from '@features/attachmodal/contracts.ts';
import { createAttachCameraElements, requireAttachModalButton, requireAttachModalChild } from '@features/attachmodal/elements.ts';
import { activateAttachTab, attachTabComponentId, createAttachTabsComponent, requireAttachTabAvailable, resolveInitialAttachTab, syncAttachTabAvailability, syncAttachTabBadges } from '@features/attachmodal/tabs.ts';

type AttachSession = {
    run: LifecycleRun;
    scope: AbortSignalScope;
    modal: HTMLElement;
    once: AsyncOnceGuard<void>;
    cleanups: (() => void)[];
    tabs: TabsComponent | null;
    content: AttachModalContent | null;
    camera: AttachCameraRuntime | null;
    busy: Map<HTMLButtonElement, BusyDisabledToken>;
    tab: AttachModalTab;
};

const focusTokens = (tab: AttachModalTab): readonly string[] => {
    if (tab === 'camera') return ['camera-shutter'];
    if (tab === 'browse') return ['search'];
    if (tab === 'soaiLink') return ['soai-link-input'];
    if (tab === 'knowledge') return ['knowledge-dropzone', 'knowledge-file-button', 'knowledge-folder-button'];
    return ['dropzone', 'upload-file-button', 'upload-folder-button'];
};

class AttachModalController {
    readonly #consumer: AttachModalConsumer;
    readonly #lifetime = new LifecycleScope();
    readonly #sequence = new SequenceToken();
    #session: AttachSession | null = null;
    #disposed = false;

    constructor(consumer: AttachModalConsumer) {
        this.#consumer = consumer;
    }

    open(options: AttachModalOpenOptions = {}): void {
        if (this.#disposed || this.#consumer.signal()?.aborted) return;
        const session = this.#session ?? this.#begin(options);
        const tab = resolveInitialAttachTab(this.#consumer, session.modal, options, session.tab);
        session.tab = tab;
        const token = this.#sequence.next();
        this.#consumer.run('chat:attachModalOpen', async () => {
            try {
                await session.once.run(() => this.#initialize(session));
                if (!this.#current(session, token)) return;
                await this.#select(session, tab, token);
                if (!this.#current(session, token)) return;
                this.#schedulePresentation(session, tab, token);
            } catch (error) {
                if (!this.#current(session) || isAbortError(error)) return;
                this.#end(session);
                throw ensureError(error);
            }
        });
    }

    onModalClosed(): void {
        const session = this.#session;
        if (session !== null) this.#end(session);
    }

    disposeForPageDestroy(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        const session = this.#session;
        if (session === null) return;
        this.#end(session);
        this.#consumer.presenter.close(ATTACH_MODAL_ID, { force: true, reason: 'owner-cancelled', restoreFocus: false });
    }

    #current(session: AttachSession, token?: number): boolean {
        return this.#session === session && this.#lifetime.isCurrent(session.run) && !session.scope.signal.aborted && !this.#disposed && (token === undefined || this.#sequence.isActive(token));
    }

    #begin(options: AttachModalOpenOptions): AttachSession {
        const modal = this.#consumer.presenter.requireElement(ATTACH_MODAL_ID);
        const run = this.#lifetime.begin();
        const scope = createAbortSignalScope([run.signal, this.#consumer.signal()]);
        const session: AttachSession = { run, scope, modal, once: new AsyncOnceGuard<void>(), cleanups: [], tabs: null, content: null, camera: null, busy: new Map(), tab: resolveInitialAttachTab(this.#consumer, modal, options) };
        this.#session = session;
        bindManagedModalLifecycleEvents({ signal: scope.signal, resolveModalElement: () => modal, bindings: [createManagedModalCloseBinding(ATTACH_MODAL_ID, this)] });
        scope.signal.addEventListener(
            'abort',
            () => {
                if (this.#session === session) this.disposeForPageDestroy();
            },
            { once: true }
        );
        return session;
    }

    async #initialize(session: AttachSession): Promise<void> {
        if (!this.#current(session)) return;
        session.content = this.#consumer.createContent({ modal: session.modal, signal: session.scope.signal, isCurrent: () => this.#current(session), addCleanup: (cleanup) => session.cleanups.push(cleanup) });
        session.cleanups.push(() => session.content?.deactivate());
        if (this.#consumer.policy.enabledTabs.includes('camera')) {
            session.camera = createCameraCaptureRuntime(createAttachCameraElements(session.modal), session.scope.signal);
            session.cleanups.push(() => session.camera?.dispose());
        }
        const tabs = createAttachTabsComponent(session.modal, session.tab, this.#consumer.policy.enabledTabs, (tab) => this.open({ initialTab: tab }));
        session.tabs = tabs;
        await tabs.initialize();
        if (!this.#current(session)) return;
        session.cleanups.push(
            this.#consumer.subscribeChanges(() => {
                if (this.#current(session)) this.#sync(session);
            })
        );
        bindTypedResolvedDataActionListener({ root: session.modal, signal: session.scope.signal, eventType: 'click', isAction: isAttachModalAction, preventDefault: 'always', onAction: ({ action, actionElement, event }) => this.#action(session, action, actionElement, event) });
        this.#sync(session);
    }

    #sync(session: AttachSession): void {
        if (session.tabs === null) return;
        syncAttachTabAvailability(this.#consumer, session.tabs);
        syncAttachTabBadges(this.#consumer, session.tabs);
        session.camera?.setAvailable(this.#consumer.isAvailable('camera'));
        const counts = this.#consumer.counts();
        for (const tab of this.#consumer.policy.enabledTabs) {
            const button = requireAttachModalButton(session.modal, `${tab === 'soaiLink' ? 'soai-link' : tab}-remove-all`);
            button.hidden = counts[tab] === 0;
            if (!session.busy.has(button)) {
                button.disabled = counts[tab] === 0;
                button.setAttribute('aria-disabled', String(button.disabled));
            }
        }
    }

    async #select(session: AttachSession, tab: AttachModalTab, token: number): Promise<void> {
        requireAttachTabAvailable(this.#consumer, tab);
        if (session.tabs === null) return;
        session.tabs.activeTab = attachTabComponentId(tab);
        activateAttachTab(session.modal, tab, this.#consumer.policy.enabledTabs);
        session.modal.dataset['chatAttachActiveTab'] = tab;
        session.camera?.deactivate();
        session.content?.deactivate();
        session.content?.activate(tab);
        if (!this.#current(session, token)) return;
        this.#consumer.presenter.open(ATTACH_MODAL_ID);
        if (tab === 'camera') await session.camera?.activate();
        if (!this.#current(session, token)) return;
    }

    #schedulePresentation(session: AttachSession, tab: AttachModalTab, token: number): void {
        getRequestAnimationFrame()(() => {
            if (!this.#current(session, token) || !session.modal.isConnected) return;
            const prefix = tab === 'soaiLink' ? 'soai-link' : tab;
            const list = requireAttachModalChild(session.modal, `${prefix}-${tab === 'knowledge' ? 'documents-list' : 'list'}`);
            checkerboardService.updateCheckerboard(list, tab === 'knowledge' ? '.rag-document-item' : '.chat-attach-draft-attachment-row');
            for (const name of focusTokens(tab)) {
                const element = requireAttachModalChild(session.modal, name);
                if (element.hidden || element.getClientRects().length === 0 || (element instanceof HTMLButtonElement && element.disabled)) continue;
                element.focus({ preventScroll: true });
                break;
            }
        });
    }

    async #action(session: AttachSession, action: AttachModalAction, element: HTMLElement, event: Event): Promise<void> {
        if (!this.#current(session)) return;
        const button = element instanceof HTMLButtonElement ? element : null;
        if (button !== null && session.busy.has(button)) return;
        const camera = session.camera;
        const intake = action === ATTACH_MODAL_ACTIONS.CAMERA_USE ? this.#consumer.captureCamera() : null;
        if (button !== null) session.busy.set(button, setBusyDisabledState(button, { isBusy: true, createToken: createBusyDisabledToken }));
        try {
            if (action === ATTACH_MODAL_ACTIONS.REMOVE_ALL) {
                const source = this.#consumer.policy.enabledTabs.find((tab) => requireAttachModalButton(session.modal, `${tab === 'soaiLink' ? 'soai-link' : tab}-remove-all`) === element);
                if (source === undefined) throw new Error('Attachment removal requires an owning tab');
                await this.#consumer.removeAll(source);
            } else if (action === ATTACH_MODAL_ACTIONS.CAMERA_USE && camera !== null && intake !== null) {
                requireAttachTabAvailable(this.#consumer, 'camera');
                const file = await camera.useCapturedFile();
                if (file === null || !this.#current(session) || !intake.scope.isCurrent()) return;
                this.#consumer.presenter.close(ATTACH_MODAL_ID);
                await intake.submit(file);
            } else if (camera !== null && (action === ATTACH_MODAL_ACTIONS.CAMERA_SHUTTER || action === ATTACH_MODAL_ACTIONS.CAMERA_RETAKE || action === ATTACH_MODAL_ACTIONS.CAMERA_SWITCH)) {
                requireAttachTabAvailable(this.#consumer, 'camera');
                if (action === ATTACH_MODAL_ACTIONS.CAMERA_SHUTTER) await camera.capture();
                if (action === ATTACH_MODAL_ACTIONS.CAMERA_RETAKE) await camera.retake();
                if (action === ATTACH_MODAL_ACTIONS.CAMERA_SWITCH) await camera.switchCamera();
            } else if (await session.content?.handleAction(action, element, event)) {
                if (this.#current(session)) this.#consumer.presenter.close(ATTACH_MODAL_ID);
            }
        } finally {
            const busy = button === null ? undefined : session.busy.get(button);
            if (button !== null && busy !== undefined) {
                session.busy.delete(button);
                if (this.#current(session)) setBusyDisabledState(button, { isBusy: false, token: busy });
            }
            if (this.#current(session)) this.#sync(session);
        }
    }

    #end(session: AttachSession): void {
        if (this.#session !== session) return;
        this.#session = null;
        this.#sequence.invalidate();
        this.#lifetime.abort();
        session.once.dispose();
        const failures: Error[] = [];
        for (const [button, token] of session.busy)
            runCleanupStepCollectingFailure(() => {
                setBusyDisabledState(button, { isBusy: false, token });
            }, failures);
        session.busy.clear();
        for (const cleanup of session.cleanups.reverse()) runCleanupStepCollectingFailure(cleanup, failures);
        session.cleanups.length = 0;
        runCleanupStepCollectingFailure(session.scope.cleanup, failures);
        const tabs = session.tabs;
        session.tabs = null;
        const cleanup =
            tabs === null
                ? Promise.resolve()
                : runAsyncCleanupStepCollectingFailure(async () => {
                      await tabs.destroy();
                  }, failures);
        void cleanup
            .then(() => {
                throwCollectedCleanupFailures(failures);
            })
            .catch((error) => {
                this.#consumer.reportCleanupFailure(ensureError(error));
            });
    }
}

export { AttachModalController };
