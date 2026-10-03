/* SoAI - Bidirectional localization text boundaries [frontend/assets/ts/core/localization/textDirection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const hasRtlScriptLetters = (text: string): boolean => /(?=[\p{Script=Arabic}\p{Script=Hebrew}])\p{Letter}/u.test(text);

const isolateLtrText = (text: string): string => `\u2066${text}\u2069`;

const countUnisolatedTextCharacters = (text: string): number => Array.from(text.replace(/[\u2066-\u2069]/gu, '')).length;

export { countUnisolatedTextCharacters, hasRtlScriptLetters, isolateLtrText };
