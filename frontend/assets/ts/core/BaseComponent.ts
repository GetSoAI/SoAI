/* SoAI - Shared frontend base component [frontend/assets/ts/core/BaseComponent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { LifecycleModel, type PageContext } from '@core/LifecycleModel.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { TimerOptions } from '@core/lifecyclemodel/types.ts';

interface ComponentOptions {
    componentName?: string;
    pageContext?: PageContext | null;
}

type ComponentOptionValue = JsonValue | CallableFunction | ArrayBufferView | null | undefined;
type ComponentOptionsRecord<TOptions = ComponentOptions> = Partial<TOptions>;
type ComponentEventDetail<TDetail = ComponentOptionValue> = TDetail | null;

interface ResourceSnapshot {
    eventListeners?: number;
    timeouts?: number;
    intervals?: number;
    animationFrames?: number;
    disposables?: number;
}

interface ComponentState {
    name: string;
    isInitialized: boolean;
    isDestroyed: boolean;
    eventListeners: number;
    timers: number;
    animationFrames: number;
    disposables: number;
    element: boolean;
}

class BaseComponent<TOptions = ComponentOptions> extends LifecycleModel {
    #element: HTMLElement | null;
    #options: ComponentOptionsRecord<TOptions>;

    constructor(element: HTMLElement | null, options: ComponentOptionsRecord<TOptions> & ComponentOptions = {}, defaultOptions: ComponentOptionsRecord<TOptions> = {}) {
        const componentName = options.componentName || (element?.id ? `component:${element.id}` : new.target?.name || 'BaseComponent');
        const pageContext = options.pageContext ?? null;
        const { componentName: _cn, pageContext: _pc, ...rest } = options;
        super({ name: componentName, pageContext });
        this.#element = element || null;
        this.#options = { ...defaultOptions, ...rest };
    }

    get element(): HTMLElement | null {
        return this.#element;
    }

    get options(): ComponentOptionsRecord<TOptions> {
        return this.#options;
    }

    set options(value: ComponentOptionsRecord<TOptions>) {
        this.#options = value;
    }

    async initialize(...inputArguments: (JsonValue | null)[]): Promise<boolean> {
        const initialized = await super.initializeLifecycle(...inputArguments);
        if (initialized) {
            this.emit('initialized');
        }
        return initialized;
    }

    override async afterInitialize(): Promise<void> {
        await this.bindEvents();
    }

    bindEvents(): void | Promise<void> {}

    override async destroy(...inputArguments: (JsonValue | null)[]): Promise<boolean> {
        const destroyed = await super.destroy(...inputArguments);
        if (destroyed) {
            this.emit('destroyed');
        }
        return destroyed;
    }

    addEventListener(target: EventTarget, event: string, handler: EventListener, options: AddEventListenerOptions = {}): () => void {
        if (this.isDestroyed) {
            return () => {};
        }
        return this.lifecycleResources.addEventListener(target, event, handler, options);
    }

    setTimer(callback: () => void, delay: number, options?: TimerOptions): number | null {
        if (this.isDestroyed) return null;
        return this.lifecycleResources.setTimer(callback, delay, options);
    }

    clearTimer(timerId: number | null | undefined): void {
        this.lifecycleResources.clearTimer(timerId);
    }

    setTimeout(callback: () => void, delay: number): number | null {
        if (this.isDestroyed) {
            return null;
        }
        return this.lifecycleResources.setTimer(
            () => {
                if (!this.isDestroyed) {
                    callback();
                }
            },
            delay,
            { repeat: false }
        );
    }

    setInterval(callback: () => void, delay: number): number | null {
        if (this.isDestroyed) {
            return null;
        }
        return this.lifecycleResources.setTimer(
            () => {
                if (!this.isDestroyed) {
                    callback();
                }
            },
            delay,
            { repeat: true }
        );
    }

    emit<TDetail>(eventName: string, detail: ComponentEventDetail<TDetail> = null): void {
        if (!this.#element) {
            return;
        }
        this.#element.dispatchEvent(
            new CustomEvent(eventName, {
                detail,
                bubbles: true,
                cancelable: true
            })
        );
    }

    getUI(selector: string, context: Element | null = null): Element | null {
        return dom.resolve(selector, context || this.#element);
    }

    queryUI(selector: string, context: Element | null = null): Element[] {
        return dom.resolveAll(selector, context || this.#element);
    }

    $(selector: string): Element | null {
        return this.getUI(selector);
    }

    $$(selector: string): Element[] {
        return this.queryUI(selector);
    }

    getOption<TKey extends Extract<keyof TOptions, string>>(key: TKey): ComponentOptionsRecord<TOptions>[TKey] {
        return this.#options[key];
    }

    setOption<TKey extends Extract<keyof TOptions, string>>(key: TKey, value: TOptions[TKey]): void {
        this.#options[key] = value;
        this.emit('optionChanged', { key, value });
    }

    setOptions(newOptions: ComponentOptionsRecord<TOptions>): void {
        Object.assign(this.#options, newOptions);
        this.emit('optionsChanged', newOptions);
    }

    isValid(): boolean {
        return Boolean(this.#element) && this.isInitialized && !this.isDestroyed;
    }

    getState(): ComponentState {
        const trackerState: ResourceSnapshot = this.resources ? this.resources.snapshot() : {};
        return {
            name: this.constructor.name,
            isInitialized: this.isInitialized,
            isDestroyed: this.isDestroyed,
            eventListeners: trackerState.eventListeners || 0,
            timers: (trackerState.timeouts || 0) + (trackerState.intervals || 0),
            animationFrames: trackerState.animationFrames || 0,
            disposables: trackerState.disposables || 0,
            element: Boolean(this.#element)
        };
    }
}

export { BaseComponent };
export type { ComponentEventDetail, ComponentOptionValue, ComponentOptions, ComponentOptionsRecord, ComponentState };
