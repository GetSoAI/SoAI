/* SoAI - Shared assertion primitives [frontend/assets/ts/core/assertions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getTypeOf, isObject, isPlainObject, type TypeOfResult } from '@core/typeGuards.ts';

interface AssertionRecord {
    [key: string]: AssertionValue;
}

type ErrorConstructor = new (message?: string) => Error;
type AssertionValue = string | number | boolean | bigint | symbol | CallableFunction | ErrorConstructor | AssertionRecord | readonly AssertionValue[] | null | undefined | void;
type Constructor<T> = abstract new (...inputArguments: never[]) => T;
const isPlainAssertionObject = (value: AssertionValue): value is AssertionRecord => isPlainObject(value);

const assertNever = (value: never, message: string): never => {
    void value;
    throw new Error(message);
};

function assertObject(value: AssertionValue, description: string): asserts value is AssertionRecord {
    if (!isObject(value)) {
        throw new Error(`${description} must be a record`);
    }
}

const requireObject = (value: AssertionValue, description: string): AssertionRecord => {
    assertObject(value, description);
    return value;
};

function assertString(value: AssertionValue, description: string): asserts value is string {
    if (typeof value !== 'string') {
        throw new Error(`${description} must be a string`);
    }
}

const requireString = (value: AssertionValue, description: string): string => {
    assertString(value, description);
    return value;
};

function assertNumber(value: AssertionValue, description: string): asserts value is number {
    if (typeof value !== 'number' || Number.isNaN(value)) {
        throw new Error(`${description} must be a valid number`);
    }
}

const requireNumber = (value: AssertionValue, description: string): number => {
    assertNumber(value, description);
    return value;
};

function assertBoolean(value: AssertionValue, description: string): asserts value is boolean {
    if (typeof value !== 'boolean') {
        throw new Error(`${description} must be a boolean`);
    }
}

const requireBoolean = (value: AssertionValue, description: string): boolean => {
    assertBoolean(value, description);
    return value;
};

function assertArray(value: AssertionValue, description: string): asserts value is AssertionValue[] {
    if (!Array.isArray(value)) {
        throw new Error(`${description} must be an array`);
    }
}

const requireArray = (value: AssertionValue, description: string): AssertionValue[] => {
    assertArray(value, description);
    return value;
};

function assertNonNull<T>(value: T | null | undefined, description: string): asserts value is T {
    if (value === null || value === undefined) {
        throw new Error(`${description} cannot be null or undefined`);
    }
}

const requireNonNull = <T>(value: T | null | undefined, description: string): T => {
    assertNonNull(value, description);
    return value;
};

interface AssertNonEmptyStringOptions {
    ErrorType?: ErrorConstructor;
    message?: string;
}

const isErrorConstructor = (value: AssertionValue): value is ErrorConstructor => typeof value === 'function';

const assertNonEmptyString = (value: AssertionValue, description: string, options: AssertNonEmptyStringOptions = {}): string => {
    const ErrorType = isErrorConstructor(options.ErrorType) ? options.ErrorType : Error;
    const message = options.message ?? `${description} must be a non-empty string`;
    if (typeof value !== 'string') {
        throw new ErrorType(message);
    }
    const trimmed = value.trim();
    if (!trimmed) {
        throw new ErrorType(message);
    }
    return trimmed;
};

interface RequireValueOptions {
    ErrorType?: ErrorConstructor;
    message?: string;
}

const requireFiniteNumber = (value: AssertionValue, description: string, options: RequireValueOptions = {}): number => {
    const ErrorType = isErrorConstructor(options.ErrorType) ? options.ErrorType : Error;
    const message = options.message ?? `${description} must be a finite number`;
    if (typeof value !== 'number' || !Number.isFinite(value)) {
        throw new ErrorType(message);
    }
    return value;
};

const optionalFiniteNumber = (value: AssertionValue, description: string, options: RequireValueOptions = {}): number | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return requireFiniteNumber(value, description, options);
};

const requireInteger = (value: AssertionValue, description: string, options: RequireValueOptions = {}): number => {
    const ErrorType = isErrorConstructor(options.ErrorType) ? options.ErrorType : Error;
    const message = options.message ?? `${description} must be an integer`;
    if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value)) {
        throw new ErrorType(message);
    }
    return value;
};

const requireNonNegativeInteger = (value: AssertionValue, description: string, options: RequireValueOptions = {}): number => {
    const ErrorType = isErrorConstructor(options.ErrorType) ? options.ErrorType : Error;
    const message = options.message ?? `${description} must be a non-negative integer`;
    if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
        throw new ErrorType(message);
    }
    return value;
};

const requirePlainObject = (value: AssertionValue, description: string, options: RequireValueOptions = {}): AssertionRecord => {
    const ErrorType = isErrorConstructor(options.ErrorType) ? options.ErrorType : Error;
    const message = options.message ?? `${description} must be a plain record`;
    if (!isPlainAssertionObject(value)) {
        throw new ErrorType(message);
    }
    return value;
};

const requireBooleanValue = (value: AssertionValue, description: string, options: RequireValueOptions = {}): boolean => {
    const ErrorType = isErrorConstructor(options.ErrorType) ? options.ErrorType : Error;
    const message = options.message ?? `${description} must be boolean`;
    if (typeof value !== 'boolean') {
        throw new ErrorType(message);
    }
    return value;
};

const assertNonEmpty = (value: AssertionValue, description: string): void => {
    if (typeof value === 'string' && value.trim().length === 0) {
        throw new Error(`${description} cannot be an empty string`);
    }
    if (Array.isArray(value) && value.length === 0) {
        throw new Error(`${description} cannot be an empty array`);
    }
    if (isObject(value) && Object.keys(value).length === 0) {
        throw new Error(`${description} cannot be an empty record`);
    }
};

function assertInstanceOf<T extends AssertionValue>(value: AssertionValue, expectedClass: Constructor<T>, description: string): asserts value is T {
    if (!(value instanceof expectedClass)) {
        const className = expectedClass.name || 'unknown class';
        throw new Error(`${description} must be an instance of ${className}`);
    }
}

const assertType = (value: AssertionValue, expectedType: TypeOfResult, description: string): void => {
    if (getTypeOf(value) !== expectedType) {
        throw new Error(`${description} must be of type ${expectedType}, got ${getTypeOf(value)}`);
    }
};

function assert(condition: AssertionValue, message: string): asserts condition {
    if (!condition) {
        throw new Error(message);
    }
}

export { assert, assertObject, requireObject, assertString, requireString, assertNumber, requireNumber, requireFiniteNumber, optionalFiniteNumber, requireInteger, requireNonNegativeInteger, requirePlainObject, requireBooleanValue, assertBoolean, requireBoolean, assertArray, requireArray, assertNonNull, requireNonNull, assertNonEmptyString, assertNonEmpty, assertInstanceOf, assertType, assertNever };

export type { AssertNonEmptyStringOptions, AssertionValue, AssertionRecord };
