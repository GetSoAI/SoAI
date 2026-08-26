/* SoAI - Shared frontend DOM mapping [frontend/assets/ts/core/dom/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMUpdateServiceRuntime } from '@core/dom/internalContracts.ts';

const normalizeClassList = (runtime: DOMUpdateServiceRuntime, classes: string | string[]): string[] => {
    const values = runtime.dependencies.ensureArray(classes);
    return values.flatMap((value) => {
        const text = runtime.dependencies.toTrimmedString(value) ?? runtime.dependencies.toString(value);
        return text.trim().split(/\s+/).filter(Boolean);
    });
};

const normalizeNodes = (runtime: DOMUpdateServiceRuntime, children: Node | Node[]): Node[] => {
    const list = runtime.dependencies.ensureArray(children);
    return list.filter((child): child is Node => runtime.dependencies.isNode(child));
};

export { normalizeClassList, normalizeNodes };
