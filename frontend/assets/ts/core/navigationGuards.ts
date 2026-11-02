/* SoAI - Shared frontend navigation guards [frontend/assets/ts/core/navigationGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { navigationResult } from '@core/navigationMiddleware.ts';
import type { NavigationResultType, NavigationContext, PageMountScope, PresentationOwner, NavigationProtectionApproval } from '@core/routing/router/types.ts';
import { isFunction, isObject, isString, isSymbol } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

import { isPresentationOwnerCurrent, requirePresentationOwnerActive } from '@core/presentationOwner.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { EventBus } from '@core/EventBus.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

type GuardFunction = (context: NavigationContext) => Promise<boolean | undefined | NavigationResultType> | boolean | undefined | NavigationResultType;

interface GuardOptions {
    readonly owner: PresentationOwner;
    hasUnsavedChanges?: () => boolean;
    getProtectionRevision?: () => number | string;
    isDestructionBlocked?: () => boolean;
    subscribeProtection?: (listener: () => void) => () => void;
    id?: string | symbol | undefined;
}

interface GuardRegistry {
    register: (guard: GuardFunction, options: GuardOptions) => () => void;
    list: (owner?: PageMountScope | null) => GuardRegistration[];
    revision: (owner: PageMountScope | null) => { page: number; global: number };
    isCurrent: (registration: GuardRegistration) => boolean;
    subscribe: (listener: () => void) => () => void;
}

interface GuardRegistration {
    readonly owner: PresentationOwner;
    hasUnsavedChanges: (() => boolean) | null;
    getProtectionRevision: (() => number | string) | null;
    isDestructionBlocked: (() => boolean) | null;
    key: string | symbol;
    guard: GuardFunction;
}

interface UnsavedChangesGuardOptions {
    readonly owner: PresentationOwner;
    hasUnsavedChanges: () => boolean;
    shouldPromptOnNavigation?: (context: NavigationContext) => Promise<boolean> | boolean;
    getMessage?: (() => string) | string;
    confirmNavigation?: (context: NavigationContext) => Promise<boolean> | boolean;
    id?: string | symbol;
    scope?: Window | null;
    addEventListener?: EventBinderFunctionValue;
}

type EventBinderFunctionValue = (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => () => void;

const isNavigationResultType = (value: NavigationResultType | boolean | null | undefined): value is NavigationResultType => {
    if (!isObject(value)) return false;
    const status = value['status'];
    if (status !== 'continue' && status !== 'blocked' && status !== 'redirect') {
        return false;
    }
    if (status === 'redirect') {
        return isString(value['target']) && value['target'].trim().length > 0;
    }
    return true;
};

const createGuardRegistry = (): GuardRegistry => {
    const changes = new EventBus();
    const owners = new Map<PresentationOwner, Map<string | symbol, GuardRegistration>>();
    const revisions = new WeakMap<PresentationOwner, number>();
    let globalRevision = 0;
    const advance = (owner: PresentationOwner): void => {
        revisions.set(owner, (revisions.get(owner) ?? 0) + 1);
        if (owner.type === 'global') globalRevision += 1;
        changes.emit('changed');
    };
    const register = (guard: GuardFunction, options: GuardOptions): (() => void) => {
        if (!isFunction(guard)) throw new Error('Navigation guard must be a function');
        const { owner } = options;
        requirePresentationOwnerActive(owner);
        const key = isString(options.id) && options.id ? options.id : isSymbol(options.id) ? options.id : Symbol('navigation-guard');
        const entries = owners.get(owner) ?? new Map<string | symbol, GuardRegistration>();
        owners.set(owner, entries);
        const registration: GuardRegistration = { key, guard, owner, hasUnsavedChanges: options.hasUnsavedChanges ?? null, getProtectionRevision: options.getProtectionRevision ?? null, isDestructionBlocked: options.isDestructionBlocked ?? null };
        entries.set(key, registration);
        let releaseProtection: (() => void) | null = null;
        try {
            releaseProtection =
                options.subscribeProtection?.(() => {
                    if (entries.get(key) === registration) changes.emit('changed');
                }) ?? null;
        } catch (error) {
            if (entries.get(key) === registration) {
                entries.delete(key);
                if (!entries.size) owners.delete(owner);
                advance(owner);
            }
            throw error;
        }
        advance(owner);
        return () => {
            const release = releaseProtection;
            releaseProtection = null;
            const failures: Error[] = [];
            runCleanupStepCollectingFailure(() => {
                if (entries.get(key) !== registration) return;
                entries.delete(key);
                if (!entries.size) owners.delete(owner);
                advance(owner);
            }, failures);
            runCleanupStepCollectingFailure(() => release?.(), failures);
            throwCollectedCleanupFailures(failures);
        };
    };
    return {
        register,
        subscribe: (listener) => changes.on('changed', listener),
        list: (owner) => [...owners.values()].flatMap((entries) => [...entries.values()]).filter((entry) => owner === undefined || entry.owner.type === 'global' || entry.owner === owner),
        revision: (owner) => ({ page: owner ? (revisions.get(owner) ?? 0) : 0, global: globalRevision }),
        isCurrent: (registration) => owners.get(registration.owner)?.get(registration.key) === registration && isPresentationOwnerCurrent(registration.owner)
    };
};

const dirtyStateRegistry = createGuardRegistry();

const registerDirtyStateGuard = (guard: GuardFunction, options: GuardOptions): (() => void) => dirtyStateRegistry.register(guard, options);
const subscribeNavigationProtection = (listener: () => void): (() => void) => dirtyStateRegistry.subscribe(listener);

const resolveNavigationDestructionOwner = (owner: PageMountScope | null, authEpoch: number): PageMountScope | null => (owner?.authEpoch === authEpoch ? owner : null);

const captureNavigationProtection = (owner: PageMountScope | null): { isCurrent(): boolean; guards: readonly GuardRegistration[] } => {
    const guards = dirtyStateRegistry.list(owner);
    const revision = dirtyStateRegistry.revision(owner);
    const protections = guards.map((registration) => ({ registration, revision: registration.getProtectionRevision?.() ?? 0 }));
    const isCurrent = (): boolean => {
        const current = dirtyStateRegistry.revision(owner);
        if (current.page !== revision.page || current.global !== revision.global || (owner !== null && !owner.admission.isCurrent())) return false;
        for (const protection of protections) {
            if (!dirtyStateRegistry.isCurrent(protection.registration) || protection.revision !== (protection.registration.getProtectionRevision?.() ?? 0)) return false;
        }
        const afterQuery = dirtyStateRegistry.revision(owner);
        return current.page === afterQuery.page && current.global === afterQuery.global && (owner === null || owner.admission.isCurrent());
    };
    return { isCurrent, guards };
};

interface NavigationDestructionProtection extends NavigationProtectionApproval {
    readonly lossProtected: boolean;
    readonly explicitDestruction: 'admissible' | 'blocked';
    readonly reason: 'clean' | 'unsaved-work' | 'protection-unknown' | 'operation-active' | 'owner-unavailable' | 'protection-changed' | 'query-failed';
}

const queryNavigationProtection = (owner: PageMountScope | null): NavigationDestructionProtection => {
    if (owner && !owner.admission.isActive()) return { lossProtected: true, explicitDestruction: 'blocked', reason: 'owner-unavailable', isCurrent: () => false };
    try {
        const protection = captureNavigationProtection(owner);
        const uncertain = protection.guards.some((registration) => registration.hasUnsavedChanges === null || registration.getProtectionRevision === null);
        let lossProtected = false;
        let blocked = false;
        for (const registration of protection.guards) {
            if (!dirtyStateRegistry.isCurrent(registration)) return { lossProtected: true, explicitDestruction: 'blocked', reason: 'protection-changed', isCurrent: () => false };
            if (registration.hasUnsavedChanges?.()) lossProtected = true;
            if (registration.isDestructionBlocked?.()) blocked = true;
        }
        if (!protection.isCurrent()) return { lossProtected: true, explicitDestruction: 'blocked', reason: 'protection-changed', isCurrent: () => false };
        return { lossProtected: lossProtected || uncertain, explicitDestruction: blocked ? 'blocked' : 'admissible', reason: blocked ? 'operation-active' : lossProtected ? 'unsaved-work' : uncertain ? 'protection-unknown' : 'clean', isCurrent: protection.isCurrent };
    } catch (error) {
        errorHandler.error('navigationGuards', 'Destruction protection query failed', ensureError(error));
        return { lossProtected: true, explicitDestruction: 'blocked', reason: 'query-failed', isCurrent: () => false };
    }
};

const evaluateDirtyStateGuardBatch = async (contexts: readonly NavigationContext[]): Promise<NavigationResultType | null> => {
    const approvals = contexts.map((context) => ({ context, ...captureNavigationProtection(context.destructionOwner) }));
    const seenGlobals = new Set<GuardRegistration>();
    const isCurrent = (): boolean => approvals.every((approval) => approval.isCurrent());
    for (const approval of approvals) {
        const context = approval.context;
        for (const registration of approval.guards) {
            throwIfAborted(context.signal);
            if (!isCurrent()) return navigationResult.block('dirty-state-changed');
            if (registration.owner.type === 'global') {
                if (seenGlobals.has(registration)) continue;
                seenGlobals.add(registration);
            }
            const verdict = await registration.guard(context);
            throwIfAborted(context.signal);
            if (!isCurrent()) return navigationResult.block('dirty-state-changed');
            if (verdict === undefined || verdict === true) continue;
            if (verdict === false) return navigationResult.block('dirty-state');
            if (!isNavigationResultType(verdict)) throw new TypeError('Navigation guard returned an unsupported outcome');
            if (verdict.status !== 'continue') return verdict;
        }
        throwIfAborted(context.signal);
    }
    if (!isCurrent()) return navigationResult.block('dirty-state-changed');
    for (const approval of approvals) approval.context.approveDestruction?.({ isCurrent: approval.isCurrent });
    return null;
};

const evaluateDirtyStateGuards = (context: NavigationContext): Promise<NavigationResultType | null> => evaluateDirtyStateGuardBatch([context]);

const normalizeMessageResolver = (message: (() => string) | string | undefined): (() => string) => {
    if (isFunction(message)) {
        return () => {
            const value = message();
            return typeof value === 'string' ? value.trim() : '';
        };
    }
    const normalized = isString(message) ? message.trim() : '';
    return () => normalized;
};

const defaultEventBinder: EventBinderFunctionValue = (target, event, handler, options) => {
    target.addEventListener(event, handler, options);
    return () => target.removeEventListener(event, handler, options);
};

interface BeforeUnloadOptions {
    hasUnsavedChanges: () => boolean;
    getMessage: () => string;
    scope?: EventTarget | null | undefined;
    addEventListener?: EventBinderFunctionValue | undefined;
}

const registerBeforeUnloadPrompt = ({ hasUnsavedChanges, getMessage, scope, addEventListener }: BeforeUnloadOptions): (() => void) => {
    const target = scope || getWindow();
    if (!target || !isFunction(target.addEventListener)) return () => {};
    const binder = isFunction(addEventListener) ? addEventListener : defaultEventBinder;
    const handler = (event: BeforeUnloadEvent): string | void => {
        if (!hasUnsavedChanges()) return;
        const message = getMessage();
        if (!message) return;
        event.preventDefault();
        event.returnValue = message;
        return message;
    };
    const cleanup = binder(target, 'beforeunload', handler) || (() => {});
    return cleanup;
};

const registerUnsavedChangesGuard = ({ owner, hasUnsavedChanges, shouldPromptOnNavigation, getMessage, confirmNavigation, id, scope, addEventListener }: UnsavedChangesGuardOptions): (() => void) => {
    if (!isFunction(hasUnsavedChanges)) {
        throw new Error('registerUnsavedChangesGuard requires a hasUnsavedChanges function');
    }
    requirePresentationOwnerActive(owner);
    const resolveMessage = normalizeMessageResolver(getMessage);
    const navigationCheck = isFunction(shouldPromptOnNavigation) ? shouldPromptOnNavigation : () => hasUnsavedChanges();
    const confirm = isFunction(confirmNavigation) ? confirmNavigation : null;
    const guardCleanup = registerDirtyStateGuard(
        async (context: NavigationContext) => {
            throwIfAborted(context.signal);
            const needsPrompt = !!(await navigationCheck(context));
            throwIfAborted(context.signal);
            if (!needsPrompt) return true;
            const verdict = confirm ? await confirm(context) : false;
            throwIfAborted(context.signal);
            return verdict ?? false;
        },
        { id, owner, hasUnsavedChanges }
    );
    let beforeUnloadCleanup: () => void;
    try {
        beforeUnloadCleanup = registerBeforeUnloadPrompt({
            hasUnsavedChanges: () => isPresentationOwnerCurrent(owner) && hasUnsavedChanges(),
            getMessage: resolveMessage,
            scope,
            addEventListener
        });
    } catch (error) {
        guardCleanup();
        throw error;
    }
    return () => {
        const failures: Error[] = [];
        for (const cleanup of [beforeUnloadCleanup, guardCleanup]) {
            try {
                cleanup();
            } catch (error) {
                failures.push(ensureError(error));
            }
        }
        if (failures.length) throw new AggregateError(failures, 'Navigation protection cleanup incomplete');
    };
};

const hasNavigationLossProtection = (): boolean => {
    for (const registration of dirtyStateRegistry.list()) {
        if (!dirtyStateRegistry.isCurrent(registration)) continue;
        try {
            if (registration.hasUnsavedChanges?.() === true && dirtyStateRegistry.isCurrent(registration)) return true;
        } catch (error) {
            if (!dirtyStateRegistry.isCurrent(registration)) continue;
            errorHandler.error('navigationGuards', 'Loss protection query failed', ensureError(error));
            return true;
        }
    }
    return false;
};

export { captureNavigationProtection, resolveNavigationDestructionOwner, queryNavigationProtection, hasNavigationLossProtection, registerBeforeUnloadPrompt, registerDirtyStateGuard, evaluateDirtyStateGuards, evaluateDirtyStateGuardBatch, registerUnsavedChangesGuard, subscribeNavigationProtection };

export type { GuardFunction, GuardOptions, NavigationDestructionProtection, NavigationProtectionApproval, UnsavedChangesGuardOptions, NavigationResultType };
