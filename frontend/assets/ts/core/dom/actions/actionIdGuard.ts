/* SoAI - Shared frontend DOM actions action ID guard [frontend/assets/ts/core/dom/actions/actionIdGuard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const createActionIdSet = <T extends string>(
    ...ids: T[]
): {
    readonly set: ReadonlySet<string>;
    readonly guard: (value: string | undefined) => value is T;
} => {
    const set: ReadonlySet<string> = new Set(ids);
    const guard = (value: string | undefined): value is T => typeof value === 'string' && set.has(value);
    return { set, guard };
};

export { createActionIdSet };
