/* SoAI - Shared routing base page core actions [frontend/assets/ts/core/routing/pages/basepagecore/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isFunction, isNullOrUndefined, isObject } from '@core/typeGuards.ts';

const err = (message: string): Error => new Error(message);

const request = <T>(value: T | null | undefined, description: string): T => {
    if (isNullOrUndefined(value)) {
        throw err(`${description} is required`);
    }
    return value;
};

function requireMethod<TMethodName extends string, TTarget extends Record<TMethodName, CallableFunction>>(target: TTarget | null | undefined, methodName: TMethodName, label: string): TTarget[TMethodName];
function requireMethod<TTarget>(target: TTarget | null | undefined, methodName: string, label: string): CallableFunction;
function requireMethod<TTarget>(target: TTarget | null | undefined, methodName: string, label: string): CallableFunction {
    if (!isObject(target)) {
        throw err(`${label} is required`);
    }
    if (!hasFunctionProperty(target, methodName)) {
        throw err(`${label}.${methodName} must be a function`);
    }
    const method = target[methodName];
    if (!isFunction(method)) {
        throw err(`${label}.${methodName} must remain a function`);
    }
    return method;
}

function requestFunctionValue<TMethodName extends string, TTarget extends Record<TMethodName, CallableFunction>>(target: TTarget | null | undefined, methodName: TMethodName, description: string): TTarget[TMethodName];
function requestFunctionValue<TTarget>(target: TTarget | null | undefined, methodName: string, description: string): CallableFunction;
function requestFunctionValue<TTarget>(target: TTarget | null | undefined, methodName: string, description: string): CallableFunction {
    return requireMethod(target, methodName, description);
}

export { err, request, requestFunctionValue };
