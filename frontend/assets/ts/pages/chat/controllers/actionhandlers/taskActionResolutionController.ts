/* SoAI - Chat page task action resolution controller [frontend/assets/ts/pages/chat/controllers/actionhandlers/taskActionResolutionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface TaskActionResolutionHost {
    presentation: { actionData(actionElement: HTMLElement, name: string): string | null };
    conversation: { currentId(): string | null };
    execution: { run(operationId: string, task: () => Promise<void> | void): void };
}

interface ResolvedTaskAction {
    conversationId: string;
    taskId: string;
}

type ResolvedTaskActionRunner = (conversationId: string, taskId: string) => Promise<void>;
type ResolvedTaskPayloadRunner<TPayload> = (conversationId: string, taskId: string, payload: TPayload) => Promise<void>;
type ResolvedTaskNamedActionRunner<TAction extends string> = (conversationId: string, taskId: string, action: TAction) => Promise<void>;

const resolveTaskAction = (host: TaskActionResolutionHost, actionElement: HTMLElement, errorMessage: string): ResolvedTaskAction | null => {
    const taskId = host.presentation.actionData(actionElement, 'task-id');
    if (!taskId) {
        throw new Error(errorMessage);
    }
    const conversationId = host.conversation.currentId();
    if (!conversationId) {
        return null;
    }
    return {
        conversationId,
        taskId
    };
};

const runResolvedTaskAction = (host: TaskActionResolutionHost, actionElement: HTMLElement, operationId: string, errorMessage: string, task: (resolved: ResolvedTaskAction) => Promise<void>): void => {
    const resolved = resolveTaskAction(host, actionElement, errorMessage);
    if (!resolved) {
        return;
    }
    host.execution.run(operationId, async () => {
        await task(resolved);
    });
};

const runResolvedTaskRunner = (resolved: ResolvedTaskAction, task: ResolvedTaskActionRunner): Promise<void> => {
    return task(resolved.conversationId, resolved.taskId);
};

const runResolvedTaskPayloadRunner = <TPayload>(resolved: ResolvedTaskAction, payload: TPayload, task: ResolvedTaskPayloadRunner<TPayload>): Promise<void> => {
    return task(resolved.conversationId, resolved.taskId, payload);
};

const createResolvedTaskActionHandler = (host: TaskActionResolutionHost, operationId: string, errorMessage: string, task: ResolvedTaskActionRunner): ((actionElement: HTMLElement) => void) => {
    return (actionElement: HTMLElement): void => {
        runResolvedTaskAction(host, actionElement, operationId, errorMessage, async (resolved) => runResolvedTaskRunner(resolved, task));
    };
};

const createResolvedNamedTaskActionHandler = <TAction extends string>(host: TaskActionResolutionHost, operationId: string, errorMessage: string, action: TAction, task: ResolvedTaskNamedActionRunner<TAction>): ((actionElement: HTMLElement) => void) => {
    return createResolvedTaskActionHandler(host, operationId, errorMessage, async (conversationId, taskId) => {
        await task(conversationId, taskId, action);
    });
};

const createResolvedTaskPayloadActionHandler = <TPayload>(host: TaskActionResolutionHost, operationId: string, errorMessage: string, resolvePayload: (actionElement: HTMLElement) => TPayload | null, task: ResolvedTaskPayloadRunner<TPayload>): ((actionElement: HTMLElement) => void) => {
    return (actionElement: HTMLElement): void => {
        const payload = resolvePayload(actionElement);
        if (payload === null) {
            return;
        }
        runResolvedTaskAction(host, actionElement, operationId, errorMessage, async (resolved) => runResolvedTaskPayloadRunner(resolved, payload, task));
    };
};

export { createResolvedNamedTaskActionHandler, createResolvedTaskActionHandler, createResolvedTaskPayloadActionHandler, resolveTaskAction, runResolvedTaskAction };
export type { ResolvedTaskAction, ResolvedTaskActionRunner, ResolvedTaskNamedActionRunner, ResolvedTaskPayloadRunner, TaskActionResolutionHost };
