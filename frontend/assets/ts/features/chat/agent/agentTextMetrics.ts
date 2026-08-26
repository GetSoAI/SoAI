/* SoAI - Agent timeline text metrics [frontend/assets/ts/features/chat/agent/agentTextMetrics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const HIGH_SURROGATE_START = 0xd800;
const HIGH_SURROGATE_END = 0xdbff;
const LOW_SURROGATE_START = 0xdc00;
const LOW_SURROGATE_END = 0xdfff;

type AgentTextForwardCursor = {
    codePointIndexAtUnitIndex: (unitIndex: number) => number;
    unitIndexAtCodePointIndex: (codePointIndex: number) => number;
};

const isSurrogatePairAt = (text: string, unitIndex: number): boolean => {
    const leadingUnit = text.charCodeAt(unitIndex);
    if (leadingUnit < HIGH_SURROGATE_START || leadingUnit > HIGH_SURROGATE_END || unitIndex + 1 >= text.length) {
        return false;
    }
    const trailingUnit = text.charCodeAt(unitIndex + 1);
    return trailingUnit >= LOW_SURROGATE_START && trailingUnit <= LOW_SURROGATE_END;
};

const countAgentTextCodePoints = (text: string): number => {
    let codePointCount = 0;
    let unitIndex = 0;
    while (unitIndex < text.length) {
        unitIndex += isSurrogatePairAt(text, unitIndex) ? 2 : 1;
        codePointCount += 1;
    }
    return codePointCount;
};

const createAgentTextForwardCursor = (text: string): AgentTextForwardCursor => {
    let cursorUnitIndex = 0;
    let cursorCodePointIndex = 0;
    return {
        codePointIndexAtUnitIndex: (unitIndex: number): number => {
            if (unitIndex < cursorUnitIndex) {
                throw new Error('Agent text cursor cannot move backwards to an earlier code unit');
            }
            while (cursorUnitIndex < unitIndex && cursorUnitIndex < text.length) {
                cursorUnitIndex += isSurrogatePairAt(text, cursorUnitIndex) ? 2 : 1;
                cursorCodePointIndex += 1;
            }
            return cursorCodePointIndex;
        },
        unitIndexAtCodePointIndex: (codePointIndex: number): number => {
            if (codePointIndex < cursorCodePointIndex) {
                throw new Error('Agent text cursor cannot move backwards to an earlier code point');
            }
            while (cursorCodePointIndex < codePointIndex && cursorUnitIndex < text.length) {
                cursorUnitIndex += isSurrogatePairAt(text, cursorUnitIndex) ? 2 : 1;
                cursorCodePointIndex += 1;
            }
            return cursorUnitIndex;
        }
    };
};

export { countAgentTextCodePoints, createAgentTextForwardCursor };
export type { AgentTextForwardCursor };
