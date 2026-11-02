/* SoAI - SaveScope state container [frontend/assets/ts/core/save/scope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createMicrotaskScheduler } from '@core/primitives/microtaskScheduler.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { PreparedSaveUnit, SaveRequestOutcome, SaveScope, SaveUnit, SaveUnitResult } from '@core/save/contracts.ts';

const ensureUnitId = (value: string): string => {
    const trimmed = value.trim();
    if (!trimmed) {
        throw new Error('Save unit id must not be empty');
    }
    return trimmed;
};

const createSaveScope = ({ isCurrent = () => true, canRequestSave = () => true }: { isCurrent?: () => boolean; canRequestSave?: () => boolean } = {}): SaveScope => {
    const units = new Map<string, SaveUnit>();
    const subscribers = new Set<() => void>();
    const predicateFailures = new Map<string, true>();
    const scheduleEmit = createMicrotaskScheduler(() => {
        for (const listener of subscribers) {
            try {
                listener();
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('SaveScope', 'Subscriber failed', runtimeError);
            }
        }
    });
    let disposed = false;
    let saving = false;
    let protectionRevision = 0;
    let callbackDepth = 0;
    const notifyChanged = (): void => {
        if (disposed) return;
        protectionRevision += 1;
        scheduleEmit();
    };
    const invokeCallback = <Result>(callback: () => Result): Result => {
        callbackDepth += 1;
        try {
            return callback();
        } finally {
            callbackDepth -= 1;
        }
    };
    const ownsLifetime = (): boolean => !disposed && isCurrent();
    const ownsUnit = (unit: SaveUnit): boolean => ownsLifetime() && units.get(unit.id) === unit;

    const safeHasChanges = (unit: SaveUnit): boolean => {
        try {
            predicateFailures.delete(unit.id);
            return invokeCallback(() => unit.hasChanges());
        } catch (error) {
            predicateFailures.set(unit.id, true);
            const runtimeError = ensureError(error);
            errorHandler.error('SaveScope', `Save unit ${unit.id} hasChanges() failed`, runtimeError);
            return true;
        }
    };

    const safeIsValid = (unit: SaveUnit): boolean => {
        if (predicateFailures.has(unit.id)) {
            return false;
        }
        if (!unit.isValid) {
            return true;
        }
        try {
            return invokeCallback(() => unit.isValid?.() ?? true);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('SaveScope', `Save unit ${unit.id} isValid() failed`, runtimeError);
            return false;
        }
    };

    const getDirtyUnits = (): SaveUnit[] => {
        const dirty: SaveUnit[] = [];
        for (const unit of units.values()) {
            if (safeHasChanges(unit)) {
                dirty.push(unit);
            }
        }
        return dirty;
    };

    const areDirtyUnitsValid = (dirty: SaveUnit[]): boolean => {
        for (const unit of dirty) {
            if (!safeIsValid(unit)) {
                return false;
            }
        }
        return true;
    };

    const prepareUnit = (unit: SaveUnit): PreparedSaveUnit => {
        if (unit.prepare) {
            return invokeCallback(() => unit.prepare?.() ?? { save: () => unit.save() });
        }
        return {
            isValid: () => safeIsValid(unit),
            save: () => unit.save()
        };
    };

    const resolveUnitResult = (result: SaveUnitResult): 'saved' | 'degraded' | 'stopped' => {
        if (result === undefined) {
            return 'saved';
        }
        if (result.type === 'continue-degraded') {
            return 'degraded';
        }
        return 'stopped';
    };

    return {
        registerUnit(unit: SaveUnit): () => void {
            if (disposed) {
                throw new Error('SaveScope has been disposed');
            }
            if (!unit) {
                throw new Error('SaveScope registerUnit() requires a unit');
            }
            const id = ensureUnitId(unit.id);
            if (units.has(id)) {
                throw new Error(`SaveScope already contains a unit with id "${id}"`);
            }
            if (!isFunction(unit.hasChanges) || !isFunction(unit.save)) {
                throw new Error(`Save unit ${id} must define hasChanges() and save()`);
            }
            const isValid = unit.isValid;
            if (isValid !== undefined && !isFunction(isValid)) {
                throw new Error(`Save unit ${id} optional isValid must be a function`);
            }
            const prepare = unit.prepare;
            if (prepare !== undefined && !isFunction(prepare)) {
                throw new Error(`Save unit ${id} optional prepare must be a function`);
            }
            const getProtectionRevision = unit.getProtectionRevision;
            if (getProtectionRevision !== undefined && !isFunction(getProtectionRevision)) throw new Error(`Save unit ${id} optional getProtectionRevision must be a function`);
            const normalized: SaveUnit = {
                id,
                ...(getProtectionRevision ? { getProtectionRevision: () => getProtectionRevision() } : {}),
                hasChanges: () => unit.hasChanges(),
                save: () => unit.save(),
                ...(isValid
                    ? {
                          isValid: () => unit.isValid?.() ?? true
                      }
                    : {}),
                ...(prepare ? { prepare: () => unit.prepare?.() ?? { save: () => unit.save() } } : {})
            };
            units.set(id, normalized);
            notifyChanged();
            return (): void => {
                if (disposed) {
                    return;
                }
                if (units.get(id) !== normalized) {
                    return;
                }
                if (units.delete(id)) {
                    predicateFailures.delete(id);
                    notifyChanged();
                }
            };
        },
        hasChanges(): boolean {
            if (disposed) {
                return false;
            }
            return getDirtyUnits().length > 0;
        },
        canSave(): boolean {
            if (disposed || saving || !canRequestSave()) {
                return false;
            }
            const dirty = getDirtyUnits();
            if (!dirty.length) {
                return false;
            }
            return areDirtyUnitsValid(dirty);
        },
        async requestSave(): Promise<SaveRequestOutcome> {
            if (disposed) {
                return 'disposed';
            }
            if (saving) {
                return 'busy';
            }
            if (!canRequestSave()) return 'blocked';
            saving = true;
            notifyChanged();
            try {
                if (!ownsLifetime()) return 'stopped';
                const dirty: SaveUnit[] = [];
                for (const unit of [...units.values()]) {
                    if (!ownsUnit(unit)) return 'stopped';
                    const changed = safeHasChanges(unit);
                    if (!ownsUnit(unit)) return 'stopped';
                    if (changed) dirty.push(unit);
                }
                if (!dirty.length) return 'noChanges';
                for (const unit of dirty) {
                    if (!ownsUnit(unit)) return 'stopped';
                    const valid = safeIsValid(unit);
                    if (!ownsUnit(unit)) return 'stopped';
                    if (!valid) return 'invalid';
                }
                const preparedUnits: { unit: SaveUnit; prepared: PreparedSaveUnit }[] = [];
                for (const unit of dirty) {
                    if (!ownsUnit(unit)) return 'stopped';
                    const prepared = prepareUnit(unit);
                    if (!ownsUnit(unit)) return 'stopped';
                    preparedUnits.push({ unit, prepared });
                }
                let degraded = false;
                for (const { unit, prepared } of preparedUnits) {
                    if (!ownsUnit(unit)) return 'stopped';
                    const valid = invokeCallback(() => prepared.isValid?.() ?? true);
                    if (!valid || !ownsUnit(unit)) return 'stopped';
                    const unitOutcome = resolveUnitResult(await invokeCallback(() => prepared.save()));
                    if (!ownsUnit(unit)) return 'stopped';
                    if (unitOutcome === 'stopped') {
                        return 'stopped';
                    }
                    degraded ||= unitOutcome === 'degraded';
                }
                return degraded ? 'degraded' : 'saved';
            } finally {
                saving = false;
                notifyChanged();
            }
        },
        isSaving(): boolean {
            return saving;
        },
        isInvokingCallback: () => callbackDepth > 0,
        getProtectionRevision: () => {
            const revision = protectionRevision;
            const values = [...units.values()].map((unit) => invokeCallback(() => unit.getProtectionRevision?.() ?? 0));
            if (revision !== protectionRevision) throw new Error('Save protection changed during its query');
            return JSON.stringify([revision, ...values]);
        },
        notifyChanged,
        subscribe(listener: () => void): () => void {
            if (disposed) {
                throw new Error('SaveScope has been disposed');
            }
            subscribers.add(listener);
            return (): void => {
                subscribers.delete(listener);
            };
        },
        dispose(): void {
            if (disposed) {
                return;
            }
            disposed = true;
            protectionRevision += 1;
            units.clear();
            subscribers.clear();
            predicateFailures.clear();
        }
    };
};

export { createSaveScope };
