/* SoAI - Shared DOM data action binding [frontend/assets/ts/core/dom/dataActionBinding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertRootDataActionsAreKnown, handleDelegatedActionEvent, resolveDelegatedActionElementResult, type DelegatedActionMouseButtonMode, type DelegatedActionPreventDefaultMode, type ElementWithActionDataset } from '@core/dom/dataAction.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

type DataActionEventType = 'change' | 'click' | 'input' | 'keydown';

const DATA_ACTION_EVENT_TYPES: readonly DataActionEventType[] = ['change', 'click', 'input', 'keydown'];

interface DataActionBindingEvent<TAction extends string> {
    event: Event;
    action: TAction;
    actionElement: ElementWithActionDataset;
}

type DataActionDispatchMap<TAction extends string> = Readonly<Record<TAction, (actionEvent: DataActionBindingEvent<TAction>) => void | Promise<void>>>;

interface DataActionListenerOptions<TAction extends string> {
    root: HTMLElement;
    isAction: (value: string | undefined) => value is TAction;
    onAction: (actionEvent: DataActionBindingEvent<TAction>) => void | Promise<void>;
    beforeEvent?: ((event: Event) => boolean) | undefined;
    preventDefault?: DelegatedActionPreventDefaultMode | undefined;
    mouseButton?: DelegatedActionMouseButtonMode | undefined;
    ignoreDisabled?: boolean | undefined;
    ignorePrevented?: boolean | undefined;
    stopPropagation?: boolean | undefined;
    ignoreFormControls?: boolean | undefined;
    disabledAttributes?: readonly string[] | undefined;
}

interface BoundDataActionListenerOptions<TAction extends string> extends DataActionListenerOptions<TAction> {
    eventType: DataActionEventType;
    signal: AbortSignal;
}

interface ResolvedDataActionListenerOptions {
    root: HTMLElement;
    onAction: (actionEvent: { event: Event; actionElement: HTMLElement }) => void | Promise<void>;
    onMiss?: ((event: Event) => void | Promise<void>) | undefined;
    beforeEvent?: ((event: Event) => boolean) | undefined;
    preventDefault?: DelegatedActionPreventDefaultMode | undefined;
    mouseButton?: DelegatedActionMouseButtonMode | undefined;
    ignoreDisabled?: boolean | undefined;
    ignoreFormControls?: boolean | undefined;
    disabledAttributes?: readonly string[] | undefined;
}

interface BoundResolvedDataActionListenerOptions extends ResolvedDataActionListenerOptions {
    eventType: DataActionEventType;
    signal: AbortSignal;
}

interface TypedResolvedActionEvent<TAction extends string> {
    event: Event;
    action: TAction;
    actionElement: HTMLElement;
}

interface TypedResolvedActionMissEvent {
    event: Event;
}

interface TypedResolvedActionListenerOptions<TAction extends string> {
    root: HTMLElement;
    signal: AbortSignal;
    eventType: DataActionEventType;
    isAction: (value: string | undefined) => value is TAction;
    onAction: (actionEvent: TypedResolvedActionEvent<TAction>) => void | Promise<void>;
    onMiss?: ((missEvent: TypedResolvedActionMissEvent) => void | Promise<void>) | undefined;
    beforeEvent?: ((event: Event) => boolean) | undefined;
    preventDefault?: DelegatedActionPreventDefaultMode | undefined;
    mouseButton?: DelegatedActionMouseButtonMode | undefined;
    ignoreDisabled?: boolean | undefined;
    ignoreFormControls?: boolean | undefined;
    disabledAttributes?: readonly string[] | undefined;
}

const handleDataActionError = (error: Error): void => {
    errorHandler.error('DataActionBinding', 'Delegated action handler failed', error);
};

const trackDataActionResult = (result: void | Promise<void> | null): void => {
    if (result === null || result === undefined) {
        return;
    }
    void Promise.resolve(result).catch((error) => {
        const runtimeError = ensureError(error);
        handleDataActionError(runtimeError);
    });
};

const createDataActionHandler = <TAction extends string>(options: DataActionListenerOptions<TAction>): EventListener => {
    return (event: Event): void => {
        try {
            if (options.beforeEvent?.(event) === true) {
                return;
            }
            const result = handleDelegatedActionEvent<TAction, void | Promise<void>>(event, {
                root: options.root,
                isAction: options.isAction,
                onAction: (actionEvent): void | Promise<void> => {
                    return options.onAction({
                        event: actionEvent.event,
                        action: actionEvent.action,
                        actionElement: actionEvent.actionElement
                    });
                },
                ...(options.preventDefault ? { preventDefault: options.preventDefault } : {}),
                ...(options.mouseButton ? { mouseButton: options.mouseButton } : {}),
                ...(options.ignoreDisabled !== undefined ? { ignoreDisabled: options.ignoreDisabled } : {}),
                ...(options.ignorePrevented !== undefined ? { ignorePrevented: options.ignorePrevented } : {}),
                ...(options.stopPropagation !== undefined ? { stopPropagation: options.stopPropagation } : {}),
                ...(options.ignoreFormControls !== undefined ? { ignoreFormControls: options.ignoreFormControls } : {}),
                ...(options.disabledAttributes !== undefined ? { disabledAttributes: options.disabledAttributes } : {})
            });
            trackDataActionResult(result);
        } catch (error) {
            const runtimeError = ensureError(error);
            handleDataActionError(runtimeError);
            throw runtimeError;
        }
    };
};

const bindDataActionListener = <TAction extends string>(options: BoundDataActionListenerOptions<TAction>): void => {
    options.root.addEventListener(options.eventType, createDataActionHandler(options), { signal: options.signal });
};

const createDataActionDispatcher = <TAction extends string>(handlers: DataActionDispatchMap<TAction>): ((actionEvent: DataActionBindingEvent<TAction>) => void | Promise<void>) => {
    return (actionEvent: DataActionBindingEvent<TAction>): void | Promise<void> => {
        const handler = handlers[actionEvent.action];
        if (!handler) {
            throw new Error(`Missing data-action handler for "${actionEvent.action}"`);
        }
        return handler(actionEvent);
    };
};

const bindResolvedDataActionListener = (options: BoundResolvedDataActionListenerOptions): void => {
    options.root.addEventListener(
        options.eventType,
        (event: Event): void => {
            try {
                if (options.beforeEvent?.(event) === true) {
                    return;
                }
                const actionResult = resolveDelegatedActionElementResult({
                    root: options.root,
                    event,
                    ...(options.preventDefault ? { preventDefault: options.preventDefault } : {}),
                    ...(options.mouseButton ? { mouseButton: options.mouseButton } : {}),
                    ...(options.ignoreDisabled !== undefined ? { ignoreDisabled: options.ignoreDisabled } : {}),
                    ...(options.ignoreFormControls !== undefined ? { ignoreFormControls: options.ignoreFormControls } : {}),
                    ...(options.disabledAttributes !== undefined ? { disabledAttributes: options.disabledAttributes } : {})
                });
                if (actionResult.type === 'ignored') {
                    return;
                }
                if (actionResult.type === 'miss') {
                    trackDataActionResult(options.onMiss?.(event) ?? null);
                    return;
                }
                const result = options.onAction({
                    event,
                    actionElement: actionResult.actionElement
                });
                trackDataActionResult(result);
            } catch (error) {
                const runtimeError = ensureError(error);
                handleDataActionError(runtimeError);
                throw runtimeError;
            }
        },
        { signal: options.signal }
    );
};

const bindTypedResolvedDataActionListener = <TAction extends string>(options: TypedResolvedActionListenerOptions<TAction>): void => {
    bindResolvedDataActionListener({
        root: options.root,
        signal: options.signal,
        eventType: options.eventType,
        ...(options.beforeEvent ? { beforeEvent: options.beforeEvent } : {}),
        ...(options.preventDefault ? { preventDefault: options.preventDefault } : {}),
        ...(options.mouseButton ? { mouseButton: options.mouseButton } : {}),
        ...(options.ignoreDisabled !== undefined ? { ignoreDisabled: options.ignoreDisabled } : {}),
        ...(options.ignoreFormControls !== undefined ? { ignoreFormControls: options.ignoreFormControls } : {}),
        ...(options.disabledAttributes !== undefined ? { disabledAttributes: options.disabledAttributes } : {}),
        ...(options.onMiss ? { onMiss: (event: Event): void | Promise<void> => options.onMiss?.({ event }) } : {}),
        onAction: ({ event, actionElement }): void | Promise<void> => {
            const action = actionElement.dataset.action;
            if (!options.isAction(action)) {
                throw new Error(`Unknown data-action "${action}"`);
            }
            return options.onAction({ event, action, actionElement });
        }
    });
};

type DataActionEventMap<TAction extends string> = Partial<Record<DataActionEventType, Omit<DataActionListenerOptions<TAction>, 'root' | 'isAction'>>>;

interface DataActionListenersOptions<TAction extends string> {
    root: HTMLElement;
    signal: AbortSignal;
    isAction: (value: string | undefined) => value is TAction;
    events: DataActionEventMap<TAction>;
}

const bindDataActionListeners = <TAction extends string>(options: DataActionListenersOptions<TAction>): void => {
    for (const eventType of DATA_ACTION_EVENT_TYPES) {
        const eventOptions = options.events[eventType];
        if (!eventOptions) {
            continue;
        }
        bindDataActionListener({
            ...eventOptions,
            root: options.root,
            signal: options.signal,
            isAction: options.isAction,
            eventType
        });
    }
};

interface PageActionDispatcherOptions<TAction extends string> extends DataActionListenersOptions<TAction> {
    label: string;
    assertKnownActions?: boolean | undefined;
}

const bindPageActionDispatcher = <TAction extends string>(options: PageActionDispatcherOptions<TAction>): void => {
    if (options.assertKnownActions !== false) {
        assertRootDataActionsAreKnown(options.root, options.label, options.isAction);
    }
    bindDataActionListeners({
        root: options.root,
        signal: options.signal,
        isAction: options.isAction,
        events: options.events
    });
};

interface MultiRootPageActionDispatcherOptions<TAction extends string> {
    roots: readonly HTMLElement[];
    signal: AbortSignal;
    label: string;
    isAction: (value: string | undefined) => value is TAction;
    events: DataActionEventMap<TAction>;
    assertKnownActions?: boolean | undefined;
}

const bindMultiRootPageActionDispatcher = <TAction extends string>(options: MultiRootPageActionDispatcherOptions<TAction>): void => {
    options.roots.forEach((root, index) => {
        bindPageActionDispatcher({
            root,
            signal: options.signal,
            label: `${options.label}[${String(index)}]`,
            isAction: options.isAction,
            events: options.events,
            ...(options.assertKnownActions !== undefined ? { assertKnownActions: options.assertKnownActions } : {})
        });
    });
};

export { bindDataActionListener, bindMultiRootPageActionDispatcher, bindPageActionDispatcher, bindResolvedDataActionListener, bindTypedResolvedDataActionListener, createDataActionDispatcher };
export type { DataActionBindingEvent, DataActionDispatchMap, DataActionEventMap, DataActionEventType, MultiRootPageActionDispatcherOptions, PageActionDispatcherOptions, TypedResolvedActionEvent, TypedResolvedActionListenerOptions, TypedResolvedActionMissEvent };
