/* SoAI - Chat sketch modal session controller [frontend/assets/ts/pages/chat/controllers/modals/sketch/ChatSketchModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveDelegatedActionElement } from '@core/dom/dataAction.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { encodeCanvasImage } from '@core/media/canvasImageEncoding.ts';
import { attachBeforeCloseConfirmationGuard, attachPendingOperationCloseGuard } from '@core/modals/closeGuard.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createBusyDisabledToken, setBusyDisabledState, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { CHAT_SKETCH_ACTIONS, CHAT_SKETCH_DEFAULT_COLOR, CHAT_SKETCH_DEFAULT_TOOL, CHAT_SKETCH_FILE_NAME, CHAT_SKETCH_FILE_TYPE, CHAT_SKETCH_MODAL_ID, CHAT_SKETCH_SIZE_MAX, CHAT_SKETCH_SIZE_MIN, CHAT_SKETCH_TOOLS, ChatSketchDocument, findChatSketchTool, isChatSketchAction, normalizeChatSketchColor, type ChatSketchAction, type ChatSketchToolType } from '@features/chat/public.ts';
import { resolveChatSketchModalRefs } from '@pages/chat/controllers/modals/sketch/dom.ts';
import { SketchCanvasWidget } from '@pages/chat/controllers/modals/sketch/SketchCanvasWidget.ts';
import { SketchPointerInputController } from '@pages/chat/controllers/modals/sketch/SketchPointerInputController.ts';
import { SketchResizeController } from '@pages/chat/controllers/modals/sketch/SketchResizeController.ts';
import type { ChatSketchModalHost, ChatSketchModalRefs, ChatSketchStyle } from '@pages/chat/controllers/modals/sketch/types.ts';
import { projectChatSketchColor, projectChatSketchHistory, projectChatSketchSize, projectChatSketchTool } from '@pages/chat/controllers/modals/sketch/view.ts';

class ChatSketchModalController {
    readonly #host: ChatSketchModalHost;
    readonly #signal: AbortSignal;
    readonly #refs: ChatSketchModalRefs;
    readonly #document = new ChatSketchDocument();
    readonly #canvas: SketchCanvasWidget;
    readonly #pointer: SketchPointerInputController;
    readonly #resize: SketchResizeController;
    readonly #sizes = new Map<ChatSketchToolType, number>(CHAT_SKETCH_TOOLS.map((tool) => [tool.type, tool.defaultSize]));
    readonly #detachGuards: ReadonlyArray<() => void>;
    #tool: ChatSketchToolType = CHAT_SKETCH_DEFAULT_TOOL;
    #color = CHAT_SKETCH_DEFAULT_COLOR;
    #attachToken: BusyDisabledToken | null = null;
    #disposed = false;

    constructor(host: ChatSketchModalHost, modal: HTMLElement, signal: AbortSignal) {
        this.#host = host;
        this.#signal = signal;
        this.#refs = resolveChatSketchModalRefs(modal);
        this.#canvas = new SketchCanvasWidget(this.#refs.canvas);
        this.#pointer = new SketchPointerInputController({
            canvas: this.#refs.canvas,
            signal,
            isEnabled: () => !this.#isSubmitting() && !this.#resize.isResizing(),
            resolveStyle: () => this.#resolveStyle(),
            onPreview: (operation) => this.#canvas.preview(operation),
            onCommit: (operation) => {
                this.#document.commit(operation);
                this.#canvas.commit(operation);
                this.#projectHistory();
            },
            onCancel: () => this.#canvas.preview(null)
        });
        this.#resize = new SketchResizeController({
            stage: this.#refs.stage,
            canvas: this.#refs.canvas,
            grip: this.#refs.grip,
            signal,
            isEnabled: () => !this.#isSubmitting() && !this.#pointer.isDrawing(),
            onResize: (target) => this.#canvas.resize(target.sheetWidth, target.sheetHeight, this.#document.visibleOperations())
        });
        this.#detachGuards = [
            attachPendingOperationCloseGuard({ modal, isPending: () => this.#isSubmitting() }),
            attachBeforeCloseConfirmationGuard({
                modal,
                presenter: host.presenter,
                modalId: CHAT_SKETCH_MODAL_ID,
                shouldConfirmClose: () => this.#document.hasContent() && !this.#isSubmitting(),
                confirmClose: () => showUnsavedChangesConfirmation({ message: i18n.t('chat.sketch.discardConfirm'), confirmText: i18n.t('chat.sketch.discard') })
            })
        ];
        this.#bind();
        projectChatSketchTool(this.#refs, this.#tool);
        projectChatSketchColor(this.#refs, this.#color);
        projectChatSketchSize(this.#refs, this.#resolveSize());
        this.#projectHistory();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        for (const detach of this.#detachGuards) detach();
        this.#releaseAttachToken();
        this.#resize.dispose();
        this.#canvas.dispose();
    }

    #bind(): void {
        bindEventGroup(
            [
                { target: this.#refs.modal, type: 'click', listener: (event: Event) => this.#handleClick(event) },
                { target: this.#refs.modal.ownerDocument, type: 'keydown', listener: (event: Event) => this.#handleKeydown(event) },
                { target: this.#refs.color, type: 'input', listener: () => this.#selectColor(this.#refs.color.value) },
                { target: this.#refs.size, type: 'input', listener: () => this.#selectSize(Number(this.#refs.size.value)) }
            ],
            this.#signal
        );
    }

    #handleClick(event: Event): void {
        const actionElement = resolveDelegatedActionElement({ event, root: this.#refs.modal, ignoreDisabled: true, preventDefault: 'never' });
        if (actionElement === null) return;
        const action = actionElement.dataset.action;
        if (!isChatSketchAction(action)) {
            if (action.startsWith('sketch:')) throw new Error(`Unknown chat sketch action ${action}`);
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        this.#dispatch(action, actionElement);
    }

    #handleKeydown(event: Event): void {
        if (this.#disposed || !(event instanceof KeyboardEvent) || event.altKey || !(event.ctrlKey || event.metaKey) || !this.#ownsKeyboardFocus(event.target)) return;
        const key = event.key.toLowerCase();
        if (key !== 'z' && key !== 'y') return;
        event.preventDefault();
        this.#dispatch(key === 'y' || event.shiftKey ? CHAT_SKETCH_ACTIONS.REDO : CHAT_SKETCH_ACTIONS.UNDO, null);
    }

    #ownsKeyboardFocus(target: EventTarget | null): boolean {
        return target instanceof Node && (this.#refs.modal.contains(target) || target === this.#refs.modal.ownerDocument.body);
    }

    #dispatch(action: ChatSketchAction, element: HTMLElement | null): void {
        if (this.#disposed || this.#isSubmitting()) return;
        if (action === CHAT_SKETCH_ACTIONS.SELECT_TOOL) this.#selectTool(element?.dataset['sketchTool']);
        if (action === CHAT_SKETCH_ACTIONS.SELECT_COLOR) this.#selectColor(element?.dataset['sketchColor']);
        if (action === CHAT_SKETCH_ACTIONS.ATTACH) this.#attach();
        if (this.#pointer.isDrawing() || this.#resize.isResizing()) return;
        if (action === CHAT_SKETCH_ACTIONS.UNDO && this.#document.undo()) this.#rebuild();
        if (action === CHAT_SKETCH_ACTIONS.REDO && this.#document.redo()) this.#rebuild();
        if (action === CHAT_SKETCH_ACTIONS.CLEAR && this.#document.clear()) this.#rebuild();
    }

    #selectTool(value: string | undefined): void {
        const tool = findChatSketchTool(value);
        if (tool === null) throw new Error(`Unknown chat sketch tool ${value ?? ''}`);
        this.#tool = tool.type;
        projectChatSketchTool(this.#refs, this.#tool);
        projectChatSketchSize(this.#refs, this.#resolveSize());
    }

    #selectColor(value: string | undefined): void {
        const color = normalizeChatSketchColor(value);
        if (color === null) return;
        this.#color = color;
        projectChatSketchColor(this.#refs, color);
    }

    #selectSize(value: number): void {
        if (!Number.isFinite(value)) return;
        const size = Math.round(clampNumber(value, CHAT_SKETCH_SIZE_MIN, CHAT_SKETCH_SIZE_MAX));
        this.#sizes.set(this.#tool, size);
        projectChatSketchSize(this.#refs, size);
    }

    #resolveSize(): number {
        return this.#sizes.get(this.#tool) ?? CHAT_SKETCH_SIZE_MIN;
    }

    #resolveStyle(): ChatSketchStyle {
        return { tool: this.#tool, color: this.#color, width: this.#resolveSize() };
    }

    #rebuild(): void {
        this.#canvas.rebuild(this.#document.visibleOperations());
        this.#projectHistory();
    }

    #projectHistory(): void {
        projectChatSketchHistory(this.#refs, { canUndo: this.#document.canUndo(), canRedo: this.#document.canRedo(), hasContent: this.#document.hasContent(), submitting: this.#isSubmitting() });
    }

    #isSubmitting(): boolean {
        return this.#attachToken !== null;
    }

    #attach(): void {
        if (!this.#document.hasContent() || this.#pointer.isDrawing() || this.#resize.isResizing()) return;
        this.#attachToken = setBusyDisabledState(this.#refs.attach, { isBusy: true, createToken: createBusyDisabledToken });
        this.#projectHistory();
        terminateHandledPromise(this.#export());
    }

    async #export(): Promise<void> {
        try {
            const blob = await encodeCanvasImage(this.#canvas.exportCanvas, CHAT_SKETCH_FILE_TYPE);
            if (this.#disposed || this.#signal.aborted) return;
            this.#releaseAttachToken();
            this.#host.submit(new File([blob], CHAT_SKETCH_FILE_NAME, { type: CHAT_SKETCH_FILE_TYPE }));
        } catch (error) {
            if (this.#disposed || this.#signal.aborted) return;
            this.#host.feedback.handle(ensureError(error), 'Chat sketch export failed', { notify: false });
            this.#host.feedback.show(i18n.t('chat.sketch.exportFailed'), 'error');
            this.#releaseAttachToken();
            this.#projectHistory();
        }
    }

    #releaseAttachToken(): void {
        if (this.#attachToken === null) return;
        setBusyDisabledState(this.#refs.attach, { isBusy: false, token: this.#attachToken });
        this.#attachToken = null;
    }
}

export { ChatSketchModalController };
