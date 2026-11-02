/* SoAI - Native keyboard composition event classification [frontend/assets/ts/core/dom/keyboardComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isKeyboardCompositionEvent = (event: KeyboardEvent): boolean => event.isComposing || event.keyCode === 229;

export { isKeyboardCompositionEvent };
