/* SoAI - Shared lifecycle model contracts [frontend/assets/ts/core/lifecyclemodel/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageContext } from '@core/pagecontext/public.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { DisposableResource, EventHandler } from '@core/resourcetracker/types.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface LifecycleModelMeta {
    moduleId?: string;
    name?: string;
    type?: string;
    host?: WeakKey | null;
    pageContext?: PageContext | null;
}

interface NotificationService {
    show: (message: string, type?: NotificationType, duration?: number) => void;
    error: (message: string, duration?: number) => void;
    success: (message: string, duration?: number) => void;
    warning: (message: string, duration?: number) => void;
    info: (message: string, duration?: number) => void;
}

interface ResourceSnapshot {
    name?: string;
    status?: string;
    error?: Error | { name?: string; message?: string } | null;
}

interface ResourceState {
    status?: string;
    error?: Error | { name?: string; message?: string } | null;
}

interface SubscribeResourceOptions {
    ensureStarted?: boolean;
    onUnavailable?: (error: Error) => void;
    onError?: (error: Error) => void;
}

interface PeekStreamManagerOptions {
    required?: boolean;
}

interface GetStreamManagerOptions {
    ensureReady?: boolean;
    allowDiscovery?: boolean;
    signal?: AbortSignal | undefined;
}

interface EnsureStreamResourcesOptions {
    allowDiscovery?: boolean;
    signal?: AbortSignal;
    strict?: boolean;
}

interface TimerOptions {
    repeat?: boolean;
    immediate?: boolean;
}

interface HandleErrorOptions {
    notify?: boolean;
    severity?: 'debug' | 'info' | 'warn' | 'error';
    rethrow?: boolean;
}

interface UpdateHTMLOptions {
    escape?: boolean;
    context?: Element | Document | null;
}

interface ReplaceContentOptions {
    escape?: boolean;
    context?: Element | Document | null;
}

interface LifecycleState {
    initialized: boolean;
    destroyed: boolean;
    cleanupPerformed: boolean;
}

interface StreamManagerCacheHost {
    getCachedStreamManager(): StreamRuntimeOwners | null;
    setCachedStreamManager(manager: StreamRuntimeOwners | null): void;
    resolveGlobalStreamManager(): StreamRuntimeOwners | null;
}

interface SubscribeResourceHost {
    setTimeout(callback: (() => void) | undefined, delay: number, options?: Omit<TimerOptions, 'repeat'>): number | null;
    clearTimer(timerId: number | null | undefined): void;
    trackDisposable<T extends DisposableResource>(resource: T, cleanup?: (dataValue: T) => void): T;
    untrackDisposable(resource: DisposableResource): void;
    peekStreamManager(options?: PeekStreamManagerOptions): StreamRuntimeOwners | null;
    getStreamManager(options?: GetStreamManagerOptions): Promise<StreamRuntimeOwners>;
}

interface DeclaredResourcesHost {
    getLifecycleIdentifier(): string;
    getRequiredResources(): string[];
    getDeclaredResourcesPromise(): Promise<StreamRuntimeOwners | null> | null;
    setDeclaredResourcesPromise(promise: Promise<StreamRuntimeOwners | null> | null): void;
    clearDeclaredResourcesPromise(promise: Promise<StreamRuntimeOwners | null>): void;
    ensureStreamResources(resourceNames: string | string[], options?: EnsureStreamResourcesOptions): Promise<StreamRuntimeOwners>;
}

interface StreamResourcesHost {
    getStreamManager(options?: GetStreamManagerOptions): Promise<StreamRuntimeOwners>;
}

export type { DeclaredResourcesHost, EnsureStreamResourcesOptions, EventHandler, GetStreamManagerOptions, HandleErrorOptions, LifecycleModelMeta, LifecycleState, NotificationService, PeekStreamManagerOptions, ReplaceContentOptions, ResourceSnapshot, ResourceState, StreamManagerCacheHost, StreamResourcesHost, StreamRuntimeOwners, SubscribeResourceHost, SubscribeResourceOptions, TimerOptions, UpdateHTMLOptions };
