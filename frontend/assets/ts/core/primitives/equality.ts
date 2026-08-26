/* SoAI - Shared primitives equality [frontend/assets/ts/core/primitives/equality.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isComparableRecord = <T>(value: T): boolean => value !== null && value !== undefined && typeof value === 'object' && !Array.isArray(value);

export const arraysEqual = <T>(firstValue: readonly T[], secondValue: readonly T[]): boolean => {
    if (!Array.isArray(firstValue) || !Array.isArray(secondValue) || firstValue.length !== secondValue.length) return false;
    for (let index = 0; index < firstValue.length; index++) {
        if (firstValue[index] !== secondValue[index]) return false;
    }
    return true;
};

export const deepEqual = <TLeft, TRight>(firstValue: TLeft, secondValue: TRight): boolean => {
    const visit = <TVisit>(xCoordinate: TVisit, yCoordinate: TVisit): boolean => {
        if (xCoordinate === yCoordinate) return true;
        if ((xCoordinate === null || xCoordinate === undefined) && (yCoordinate === null || yCoordinate === undefined)) return true;
        if (xCoordinate === null || xCoordinate === undefined || yCoordinate === null || yCoordinate === undefined) return false;
        if (typeof xCoordinate !== typeof yCoordinate) return false;
        if (Array.isArray(xCoordinate) && Array.isArray(yCoordinate)) {
            if (xCoordinate.length !== yCoordinate.length) return false;
            for (let index = 0; index < xCoordinate.length; index++) {
                if (!visit(xCoordinate[index], yCoordinate[index])) return false;
            }
            return true;
        }
        if (isComparableRecord(xCoordinate) && isComparableRecord(yCoordinate)) {
            const entriesA = Object.entries(xCoordinate);
            const entriesB = Object.entries(yCoordinate);
            if (entriesA.length !== entriesB.length) return false;
            for (const [key, entryValue] of entriesA) {
                const matchingEntry = entriesB.find(([candidateKey]) => candidateKey === key);
                if (matchingEntry === undefined) return false;
                if (!visit(entryValue, matchingEntry[1])) return false;
            }
            return true;
        }
        return false;
    };
    return visit<TLeft | TRight>(firstValue, secondValue);
};
