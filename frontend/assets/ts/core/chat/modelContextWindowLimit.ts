/* SoAI - Pure chat model context-window limit resolution [frontend/assets/ts/core/chat/modelContextWindowLimit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const resolveModelContextWindowLimit = (explicitContextWindowTokens: number | null | undefined, modelContextWindowTokens: number | null | undefined): number | null => {
    if (typeof explicitContextWindowTokens === 'number' && Number.isSafeInteger(explicitContextWindowTokens) && explicitContextWindowTokens > 0) {
        return explicitContextWindowTokens;
    }
    if (typeof modelContextWindowTokens === 'number' && Number.isSafeInteger(modelContextWindowTokens) && modelContextWindowTokens > 0) {
        return modelContextWindowTokens;
    }
    return null;
};

export { resolveModelContextWindowLimit };
