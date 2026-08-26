/* SoAI - Shared state manager [frontend/assets/ts/core/state/StateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SectionTracker, type SectionCallback, type SectionData } from '@core/state/SectionTracker.ts';
import { StatusManager } from '@core/state/statusmanager/service.ts';
import type { ApiClient, AuthService, StreamManager } from '@core/state/statusmanager/contracts.ts';
import { TabStateCoordinator, type TabStateHandler } from '@core/state/TabStateCoordinator.ts';
import type { DomService, ErrorHandler } from '@core/state/types.ts';
import { UIStateManager, type SetBusyOptions, type SetButtonLoadingOptions, type ToggleHiddenOptions } from '@core/state/UIStateManager.ts';
import { createCrossTabChannel, type CrossTabChannel } from '@core/crosstab/channel.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { StatusDefinition } from '@core/state/constants.ts';

type ElementResolver = (target: string | Element | null | undefined) => HTMLElement | null;

interface StateManagerOptions {
    dom: DomService;
    errorHandler: ErrorHandler;
    resolveElement: ElementResolver;
    defaultHiddenClass: string;
    statusStreamId: string;
    apiClientProvider: () => Promise<ApiClient | null>;
    authServiceProvider: () => Promise<AuthService>;
    streamManagerProvider: () => StreamManager;
}

class StateManager {
    readonly dom: DomService;
    readonly errorHandler: ErrorHandler;
    readonly ui: UIStateManager;
    readonly status: StatusManager;
    readonly section: SectionTracker;
    readonly tab: TabStateCoordinator;
    private readonly crossTabChannels: Map<string, CrossTabChannel>;

    constructor({ dom, errorHandler, resolveElement, defaultHiddenClass, statusStreamId, apiClientProvider, authServiceProvider, streamManagerProvider }: StateManagerOptions) {
        this.dom = dom;
        this.errorHandler = errorHandler;
        this.ui = new UIStateManager({ dom: dom, resolveElement, defaultHiddenClass });
        this.status = new StatusManager({
            dom,
            errorHandler,
            statusStreamId,
            apiClientProvider,
            authServiceProvider,
            streamManagerProvider
        });
        this.section = new SectionTracker({ dom, errorHandler });
        this.tab = new TabStateCoordinator(errorHandler);
        this.crossTabChannels = new Map();
    }

    async initialize(): Promise<void> {
        await this.status.initialize();
    }

    resolve(target: string | Element | null | undefined): HTMLElement | null {
        return this.ui.resolve(target);
    }

    toggleHidden(targets: string | string[] | Element | Element[] | null | undefined, shouldHide: boolean, options: ToggleHiddenOptions = {}): void {
        this.ui.toggleHidden(targets, shouldHide, options);
    }

    setBusy(target: string | Element | null | undefined, isBusy: boolean, options: SetBusyOptions = {}): HTMLElement | null {
        return this.ui.setBusy(target, isBusy, options);
    }

    setText(target: string | Element | null | undefined, value: string | null | undefined): HTMLElement | null {
        return this.ui.setText(target, value);
    }

    setHTML(target: string | Element | null | undefined, value: string | null | undefined, options: { escape?: boolean } = {}): HTMLElement | null {
        return this.ui.setHTML(target, value, options);
    }

    updateDataset(target: string | Element | null | undefined, dataset: Record<string, string | null | undefined> = {}): HTMLElement | null {
        return this.ui.updateDataset(target, dataset);
    }

    toggleClass(targets: string | string[] | Element | Element[] | null | undefined, className: string, force?: boolean): void {
        this.ui.toggleClass(targets, className, force);
    }

    setButtonLoading(target: string | Element | null | undefined, loading: boolean, options: SetButtonLoadingOptions = {}): HTMLElement | null {
        return this.ui.setButtonLoading(target, loading, options);
    }

    getTabState(key: string, defaultValue: JsonValue | null = null): JsonValue | null {
        return this.tab.get(key, defaultValue) ?? null;
    }

    setTabState(key: string, value: JsonValue | null | undefined): void {
        this.tab.set(key, value);
    }

    removeTabState(key: string): void {
        this.tab.remove(key);
    }

    subscribeTabState(handler: TabStateHandler): () => void {
        return this.tab.subscribe(handler);
    }

    snapshotTabState(): Record<string, JsonValue | null> {
        const snapshot = this.tab.snapshot();
        const normalized: Record<string, JsonValue | null> = {};
        for (const [key, value] of Object.entries(snapshot)) {
            normalized[key] = value ?? null;
        }
        return normalized;
    }

    getCrossTabChannel = (channelId: string): CrossTabChannel => {
        if (!channelId) {
            throw new Error('Cross-tab channel requires an identifier');
        }
        const key = String(channelId);
        if (!key) {
            throw new Error('Cross-tab channel identifier must be a non-empty string');
        }
        if (!this.crossTabChannels.has(key)) {
            this.crossTabChannels.set(key, createCrossTabChannel(key, this.errorHandler));
        }
        const channel = this.crossTabChannels.get(key);
        if (!channel) {
            throw new Error(`Cross-tab channel "${key}" is missing after initialization`);
        }
        return channel;
    };

    getStatus(status: string): StatusDefinition {
        return this.status.getDefinition(status);
    }

    getStatusColor(status: string): string {
        return this.status.getColor(status);
    }

    updateStatusIndicator(element: HTMLElement, status: string): void {
        return this.status.updateIndicator(element, status);
    }

    createStatusIndicator(status: string, size?: 'small' | 'medium' | 'large'): HTMLElement {
        return this.status.createIndicator(status, size);
    }

    initializeSectionTracking(): void {
        return this.section.initialize();
    }

    subscribeSectionChanges(callback: SectionCallback): () => boolean {
        return this.section.subscribe(callback);
    }

    getCurrentSection(): SectionData | null {
        return this.section.currentSection;
    }

    forceUpdateSection(section: string, subsection?: string | null): void {
        return this.section.forceUpdate(section, subsection ?? null);
    }

    cleanup(): void {
        this.section.cleanup();
    }

    destroy(): void {
        this.section.cleanup();
        this.status.destroy();
        this.tab.destroy();
        for (const channel of this.crossTabChannels.values()) {
            channel.close();
        }
        this.crossTabChannels.clear();
    }
}

export { StateManager };

export type { StateManagerOptions, ElementResolver };
