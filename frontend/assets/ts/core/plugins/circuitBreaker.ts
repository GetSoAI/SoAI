/* SoAI - Shared plugins circuit breaker [frontend/assets/ts/core/plugins/circuitBreaker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const ACTIVE_CIRCUIT_BREAKER_STATES: ReadonlySet<string> = Object.freeze(new Set(['open', 'half-open']));

const normalizeCircuitBreakerState = <T>(state: T): string => (typeof state === 'string' ? state.toLowerCase() : '');

const isCircuitBreakerStateActive = <TState, TOpen>(state: TState, isOpen: TOpen): boolean => {
    const normalizedState = normalizeCircuitBreakerState(state);
    return isOpen === true || ACTIVE_CIRCUIT_BREAKER_STATES.has(normalizedState);
};

const requireActiveCircuitBreakerNumber = <T>(value: T, fieldName: string): number => {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    throw new Error(`Active circuit breaker payload missing numeric ${fieldName}`);
};

export { isCircuitBreakerStateActive, normalizeCircuitBreakerState, requireActiveCircuitBreakerNumber };
