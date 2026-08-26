/* SoAI - Shared primitives hash [frontend/assets/ts/core/primitives/hash.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const computeHash = (value: string): number => {
    let hash = 0;
    for (let index = 0; index < value.length; index += 1) {
        hash = (hash * 33 + value.charCodeAt(index)) >>> 0;
    }
    return hash;
};

export { computeHash };
