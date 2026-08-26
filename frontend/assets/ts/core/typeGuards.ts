/* SoAI - Shared frontend type guards [frontend/assets/ts/core/typeGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonArray, JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type Constructor<T> = abstract new (...inputArguments: never[]) => T;

type TypeOfResult = 'string' | 'number' | 'bigint' | 'boolean' | 'symbol' | 'undefined' | 'object' | 'function';
type PrimitiveValue = string | number | bigint | boolean | symbol | null | undefined | void;
type ArrayCandidate<T> = T extends readonly (infer _TValue)[] ? T : never;
type NonPrimitiveValue<T> = T extends PrimitiveValue ? never : T extends CallableFunction ? T : T extends readonly (infer _TValue)[] ? T : { [K in keyof T]: T[K] };
type NonFunctionObjectValue<T> = T extends PrimitiveValue ? never : T extends CallableFunction ? never : T extends readonly (infer _TValue)[] ? never : { [K in keyof T]: T[K] };

const isFunction = <T>(value: T): value is Extract<T, CallableFunction> => typeof value === 'function';

const isString = <T>(value: T): value is Extract<T, string> => typeof value === 'string';

const isNonEmptyString = <T>(value: T): value is Extract<T, string> => isString(value) && value.trim().length > 0;

const isNumber = <T>(value: T): value is Extract<T, number> => typeof value === 'number';

const isBoolean = <T>(value: T): value is Extract<T, boolean> => typeof value === 'boolean';

const isSymbol = <T>(value: T): value is Extract<T, symbol> => typeof value === 'symbol';

const isReferenceValue = <T>(value: T): value is NonPrimitiveValue<T> => !isNullOrUndefined(value) && Object(value) === value;

const isNonArrayReferenceValue = <T>(value: T): value is NonFunctionObjectValue<T> => isReferenceValue(value) && !isFunction(value) && !Array.isArray(value);

function isObject(value: JsonValue | null | undefined): value is JsonObject;
function isObject<T>(value: T): value is NonFunctionObjectValue<T>;
function isObject<T>(value: T): value is NonFunctionObjectValue<T> {
    return isNonArrayReferenceValue(value);
}

function isPlainObject(value: JsonValue | null | undefined): value is JsonObject;
function isPlainObject<T>(value: T): value is NonFunctionObjectValue<T>;
function isPlainObject<T>(value: T): value is NonFunctionObjectValue<T> {
    if (!isNonArrayReferenceValue(value)) {
        return false;
    }
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
}

function isArray(value: JsonValue | null | undefined): value is JsonArray;
function isArray<T>(value: T): value is ArrayCandidate<T>;
function isArray<T>(value: T): value is ArrayCandidate<T> {
    return Array.isArray(value);
}

const isStringArray = <T>(value: T): value is Extract<T, readonly string[]> => isArray(value) && value.every(isString);

const isFiniteNumber = <T>(value: T): value is Extract<T, number> => Number.isFinite(value);

const isFiniteInteger = <T>(value: T): value is Extract<T, number> => typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value);

const isNonNegativeInteger = <T>(value: T): value is Extract<T, number> => isFiniteInteger(value) && value >= 0;

const isPositiveInteger = <T>(value: T): value is Extract<T, number> => isFiniteInteger(value) && value > 0;

const isNullOrUndefined = <T>(value: T): value is Extract<T, null | undefined | void> => value == null;

const isDefined = <T>(value: T | undefined): value is T => value !== undefined;

const isNull = <T>(value: T): value is Extract<T, null> => value === null;

const isUndefined = <T>(value: T): value is Extract<T, undefined | void> => value === undefined;

const isRecordLike = <T>(value: T): value is NonPrimitiveValue<T> => isReferenceValue(value);

const scope: typeof globalThis | null = typeof globalThis === 'object' && globalThis ? globalThis : null;
const nodeCtor: typeof Node | null = typeof scope?.Node === 'function' ? scope.Node : null;
const elementCtor: typeof Element | null = typeof scope?.Element === 'function' ? scope.Element : null;
const htmlElementCtor: typeof HTMLElement | null = typeof scope?.HTMLElement === 'function' ? scope.HTMLElement : null;
const nodeListCtor: typeof NodeList | null = typeof scope?.NodeList === 'function' ? scope.NodeList : null;
const htmlCollectionCtor: typeof HTMLCollection | null = typeof scope?.HTMLCollection === 'function' ? scope.HTMLCollection : null;
const documentCtor: typeof Document | null = typeof scope?.Document === 'function' ? scope.Document : null;

const isNode = <T>(value: T): value is NonFunctionObjectValue<T> & Node => nodeCtor !== null && value instanceof nodeCtor;

const isElementNode = <T>(value: T): value is NonFunctionObjectValue<T> & Element => elementCtor !== null && value instanceof elementCtor;

const isHTMLElement = <T>(value: T): value is NonFunctionObjectValue<T> & HTMLElement => htmlElementCtor !== null && value instanceof htmlElementCtor;

const isDocumentNode = <T>(value: T): value is NonFunctionObjectValue<T> & Document => documentCtor !== null && value instanceof documentCtor;

const isNodeList = <T>(value: T): value is NonFunctionObjectValue<T> & NodeList => nodeListCtor !== null && value instanceof nodeListCtor;

const isHTMLCollection = <T>(value: T): value is NonFunctionObjectValue<T> & HTMLCollection => htmlCollectionCtor !== null && value instanceof htmlCollectionCtor;

const isThenable = <T>(value: T): value is NonPrimitiveValue<T> & PromiseLike<void> => {
    if (!isReferenceValue(value)) return false;
    return 'then' in value && isFunction(value.then);
};

const isMap = <K, V, T>(value: T): value is NonFunctionObjectValue<T> & Map<K, V> => value instanceof Map;

const isSet = <TValue, T>(value: T): value is NonFunctionObjectValue<T> & Set<TValue> => value instanceof Set;

const isBigInt = <T>(value: T): value is Extract<T, bigint> => typeof value === 'bigint';

const isInstanceOf = <T, TValue>(value: TValue, ctor: Constructor<T> | null | undefined): value is TValue & T => Boolean(ctor) && typeof ctor === 'function' && value instanceof ctor;

const getTypeOf = <T>(value: T): TypeOfResult => typeof value;

const isTypeOf = <T>(value: T, expectedType: TypeOfResult): boolean => getTypeOf(value) === expectedType;

const hasOwn = <T>(object: T, key: PropertyKey): boolean => {
    if (!isReferenceValue(object)) return false;
    return Object.prototype.hasOwnProperty.call(object, key);
};

const findPropertyDescriptor = <T>(value: NonPrimitiveValue<T>, key: PropertyKey): PropertyDescriptor | undefined => {
    let current: NonPrimitiveValue<T> | null = value;
    while (current !== null) {
        const descriptor: PropertyDescriptor | undefined = Object.getOwnPropertyDescriptor(current, key);
        if (descriptor !== undefined) return descriptor;
        const prototype: NonPrimitiveValue<T> | null = Object.getPrototypeOf(current);
        current = prototype;
    }
    return undefined;
};

const hasFunctionProperty = <T, K extends PropertyKey>(value: T, key: K): value is T & Record<K, CallableFunction> => {
    if (!isReferenceValue(value)) return false;
    const descriptor = findPropertyDescriptor(value, key);
    return descriptor !== undefined && isFunction(descriptor.value);
};

const hasFunctionProperties = <T, K extends PropertyKey>(value: T, keys: readonly K[]): value is T & Record<K, CallableFunction> => {
    if (!isReferenceValue(value)) return false;
    return keys.every((key) => hasFunctionProperty(value, key));
};

export { isFunction, isString, isNonEmptyString, isNumber, isBoolean, isSymbol, isObject, isPlainObject, isArray, isStringArray, isFiniteNumber, isFiniteInteger, isNonNegativeInteger, isPositiveInteger, isNullOrUndefined, isDefined, isNull, isUndefined, isRecordLike, isNode, isElementNode, isHTMLElement, isDocumentNode, isNodeList, isHTMLCollection, isThenable, isMap, isSet, isBigInt, isInstanceOf, getTypeOf, isTypeOf, hasOwn, hasFunctionProperty, hasFunctionProperties };

export type { Constructor, TypeOfResult };
