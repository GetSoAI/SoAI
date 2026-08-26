/* SoAI - Chat page attach modal drag-open controller [frontend/assets/ts/pages/chat/controllers/chatpage/lifecycle/attachModalDragOpenController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { getDocument, getWindow } from '@core/environment/public.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { AGENT_PLAN_MODAL_ID, ARCHIVED_CONVERSATIONS_MODAL_ID, CHAT_ATTACH_MODAL_ID, CHAT_ATTACHMENT_OVERFLOW_MODAL_ID, CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, CHAT_MEMORY_PROFILE_MODAL_ID, CHAT_TOOL_CALL_OUTPUT_MODAL_ID, CHAT_VOICE_CALL_MODAL_ID, MESSAGE_INFO_MODAL_ID } from '@features/chat/public.ts';
import { hasTransferFiles } from '@pages/chat/controllers/modals/chatattach/chatAttachDropTargetController.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';

type ChatAttachDragOpenHost = ChatConversationStateHost & {
    root: HTMLElement;
    isConversationSelectionActive(): boolean;
    isFileUploadEnabled(): boolean;
    closeAutoOpenedModal(): void;
    openUploadTab(): void;
};

const BLOCKED_MODAL_IDS = Object.freeze([CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID, CHAT_ATTACHMENT_OVERFLOW_MODAL_ID, AGENT_PLAN_MODAL_ID, ARCHIVED_CONVERSATIONS_MODAL_ID, CHAT_VOICE_CALL_MODAL_ID, CHAT_TOOL_CALL_OUTPUT_MODAL_ID, CHAT_MEMORY_PROFILE_MODAL_ID, MESSAGE_INFO_MODAL_ID]);

const isDragPointInsideElement = (event: DragEvent, element: HTMLElement): boolean => {
    const rect = measureLayoutBox(element);
    const point = measureLayoutPoint(event, element);
    return point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom;
};

const isDragPointInsideViewport = (event: DragEvent, scope: Element): boolean => {
    const point = measureLayoutPoint(event, scope);
    const viewport = measureLayoutViewport(scope);
    return point.x > 0 && point.x < viewport.width && point.y > 0 && point.y < viewport.height;
};

const bindChatAttachModalDragOpenController = (host: ChatAttachDragOpenHost, signal: AbortSignal): void => {
    const documentTarget = getDocument();
    const windowTarget = getWindow();
    let hasActiveDragSession = false;
    let requestedUploadTabForDragSession = false;
    let closeModalWhenDragSessionEnds = false;
    let attachModalWasOpenAtDragStart = false;
    const isAttachModalOpen = (): boolean => {
        return requireModalPresenter().isOpen(CHAT_ATTACH_MODAL_ID);
    };
    const shouldOpen = (): boolean => {
        if (host.conversationState.currentConversationId === null || host.isConversationSelectionActive()) {
            return false;
        }
        if (!host.isFileUploadEnabled()) {
            return false;
        }
        const presenter = requireModalPresenter();
        return !BLOCKED_MODAL_IDS.some((modalId) => presenter.isOpen(modalId));
    };
    const captureDragStart = (): void => {
        if (hasActiveDragSession) {
            return;
        }
        hasActiveDragSession = true;
        attachModalWasOpenAtDragStart = isAttachModalOpen();
    };
    const requestAutoOpenedModalClose = (): void => {
        if (!closeModalWhenDragSessionEnds) {
            return;
        }
        host.closeAutoOpenedModal();
    };
    const clearDragSession = (): void => {
        hasActiveDragSession = false;
        requestedUploadTabForDragSession = false;
        closeModalWhenDragSessionEnds = false;
        attachModalWasOpenAtDragStart = false;
    };
    const endDragSession = (): void => {
        if (hasActiveDragSession) {
            requestAutoOpenedModalClose();
        }
        clearDragSession();
    };
    const maybeOpen = (event: DragEvent): void => {
        if (!hasTransferFiles(event)) {
            return;
        }
        if (requestedUploadTabForDragSession) {
            return;
        }
        captureDragStart();
        if (!shouldOpen()) {
            return;
        }
        requestedUploadTabForDragSession = true;
        closeModalWhenDragSessionEnds = !attachModalWasOpenAtDragStart;
        host.openUploadTab();
    };
    const preventActiveFileDragDefault = (event: DragEvent): void => {
        if (!hasActiveDragSession || !hasTransferFiles(event)) {
            return;
        }
        event.preventDefault();
    };
    const handleDrop = (event: DragEvent): void => {
        preventActiveFileDragDefault(event);
        endDragSession();
    };
    const handleWindowDragEnd = (): void => {
        endDragSession();
    };
    const handleWindowBlur = (): void => {
        endDragSession();
    };
    const handleDocumentDragLeave = (event: DragEvent): void => {
        if (hasActiveDragSession && event.relatedTarget === null && (!isDragPointInsideViewport(event, host.root) || !isDragPointInsideElement(event, host.root))) {
            endDragSession();
        }
    };
    host.root.addEventListener(
        'dragenter',
        (event: DragEvent): void => {
            if (!hasTransferFiles(event)) {
                return;
            }
            maybeOpen(event);
        },
        { signal }
    );
    host.root.addEventListener(
        'dragover',
        (event: DragEvent): void => {
            if (!hasTransferFiles(event)) {
                return;
            }
            event.preventDefault();
            maybeOpen(event);
        },
        { signal }
    );
    host.root.addEventListener(
        'dragleave',
        (event: DragEvent): void => {
            if (hasActiveDragSession && !isDragPointInsideElement(event, host.root)) {
                endDragSession();
            }
        },
        { signal }
    );
    host.root.addEventListener('drop', handleDrop, { signal });
    documentTarget.addEventListener('dragover', preventActiveFileDragDefault, { signal });
    documentTarget.addEventListener('dragleave', handleDocumentDragLeave, { signal });
    documentTarget.addEventListener('drop', handleDrop, { signal });
    windowTarget.addEventListener('dragend', handleWindowDragEnd, { signal });
    windowTarget.addEventListener('blur', handleWindowBlur, { signal });
};

export { bindChatAttachModalDragOpenController };
