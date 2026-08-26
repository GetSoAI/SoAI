/* SoAI - Tasks feature task manager interaction bindings [frontend/assets/ts/features/tasks/taskmanager/taskManagerInteractionBindings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { resolveTaskStopButton } from '@features/tasks/taskmanager/service.ts';
import type { TaskManagerElements } from '@features/tasks/taskmanager/taskManagerTypes.ts';

interface TaskManagerInteractionBindingHost {
    addEventListener(target: EventTarget, event: string, handler: (event: Event) => void): () => void;
}

interface TaskManagerInteractionHandlers {
    toggle: () => void;
    collapse: () => void;
    isExpanded: () => boolean;
    stopAllPlugins: () => Promise<void>;
    handleStopButtonClick: (button: HTMLElement) => Promise<void>;
}

const bindTaskManagerInteractionBindings = (options: { host: TaskManagerInteractionBindingHost; elements: TaskManagerElements; documentRef: Document; handlers: TaskManagerInteractionHandlers }): void => {
    const { host, elements, documentRef, handlers } = options;
    host.addEventListener(elements.toggle, 'click', (event) => {
        event.stopPropagation();
        handlers.toggle();
    });
    host.addEventListener(elements.toggle, 'keydown', (event) => {
        if (!(event instanceof KeyboardEvent)) {
            return;
        }
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            handlers.toggle();
        }
    });
    host.addEventListener(elements.stopAllButton, 'click', (event) => {
        event.stopPropagation();
        terminateHandledPromise(handlers.stopAllPlugins());
    });
    host.addEventListener(elements.list, 'click', (event) => {
        const stopButton = resolveTaskStopButton(event.target);
        if (!stopButton) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        terminateHandledPromise(handlers.handleStopButtonClick(stopButton));
    });
    host.addEventListener(documentRef, 'keydown', (event) => {
        if (!(event instanceof KeyboardEvent)) {
            return;
        }
        if (event.key === 'Escape' && handlers.isExpanded()) {
            handlers.collapse();
        }
    });
};

export { bindTaskManagerInteractionBindings };
