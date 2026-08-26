/* SoAI - Chat UI task and conversation concurrency ownership [frontend/assets/ts/pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { createChatUiTaskScheduler, type ChatUiTaskScheduler } from '@pages/chat/controllers/page/uiTaskScheduler.ts';
import { ChatConcurrencyController, type ConversationActivationSnapshot } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';

interface ChatUiTaskBoundary {
    runWithBoundary<T>(operationId: string, task: () => Promise<T> | T): Promise<T>;
    getCurrentConversationId(): string | null;
}

interface ChatUiTaskScopeContract {
    readonly concurrency: ChatConcurrencyController;
    run(operationId: string, task: () => Promise<void> | void): void;
    runAsync(operationId: string, task: () => Promise<void> | void): Promise<void>;
    runResult<Result>(operationId: string, task: () => Promise<Result> | Result): Promise<Result | undefined>;
    captureConversationActivation(): ConversationActivationSnapshot;
    isConversationActivationCurrent(activation: ConversationActivationSnapshot, expectedConversationId: string): boolean;
    dispose(): void;
}

class ChatUiTaskScopeManager implements ChatUiTaskScopeContract {
    readonly concurrency = new ChatConcurrencyController();
    readonly #boundary: ChatUiTaskBoundary;
    readonly #scheduler: ChatUiTaskScheduler;

    constructor(boundary: ChatUiTaskBoundary) {
        this.#boundary = boundary;
        this.#scheduler = createChatUiTaskScheduler({
            runWithBoundary: (operationId, task) => boundary.runWithBoundary(operationId, task),
            logWarning: (message, error) => errorHandler.warn('ChatPage', message, error)
        });
    }

    run(operationId: string, task: () => Promise<void> | void): void {
        this.#scheduler.run(operationId, task);
    }

    runAsync(operationId: string, task: () => Promise<void> | void): Promise<void> {
        return this.#scheduler.runAsync(operationId, task);
    }

    runResult<Result>(operationId: string, task: () => Promise<Result> | Result): Promise<Result | undefined> {
        return this.#scheduler.runResult(operationId, task);
    }

    captureConversationActivation(): ConversationActivationSnapshot {
        return this.concurrency.captureConversationActivationSnapshot();
    }

    isConversationActivationCurrent(activation: ConversationActivationSnapshot, expectedConversationId: string): boolean {
        return this.concurrency.isConversationActivationSnapshotCurrent(activation, expectedConversationId, this.#boundary.getCurrentConversationId());
    }

    dispose(): void {
        this.#scheduler.dispose();
    }
}

export { ChatUiTaskScopeManager };
export type { ChatUiTaskBoundary, ChatUiTaskScopeContract };
export interface ChatUiTaskScopeHost {
    taskScope: ChatUiTaskScopeContract;
}
