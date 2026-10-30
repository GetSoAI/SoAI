/* SoAI - Chat sketch modal DOM resolution [frontend/assets/ts/pages/chat/controllers/modals/sketch/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { CHAT_SKETCH_ACTIONS, CHAT_SKETCH_MODAL_ID } from '@features/chat/public.ts';
import type { ChatSketchModalRefs } from '@pages/chat/controllers/modals/sketch/types.ts';

const requireUiElement = <T extends HTMLElement>(modal: HTMLElement, token: string, constructor: new (...inputArguments: never[]) => T, label: string): T => {
    const element = dom.resolve(modalUiSelector(CHAT_SKETCH_MODAL_ID, token), modal);
    if (!(element instanceof constructor)) throw new Error(`Chat sketch ${label} is unavailable`);
    return element;
};

const requireActionButtons = (modal: HTMLElement, action: string, label: string): readonly HTMLButtonElement[] => {
    const buttons = dom.resolveAll(`[data-action="${action}"]`, modal).filter((element): element is HTMLButtonElement => element instanceof HTMLButtonElement);
    if (buttons.length === 0) throw new Error(`Chat sketch ${label} are unavailable`);
    return buttons;
};

const resolveChatSketchModalRefs = (modal: HTMLElement): ChatSketchModalRefs => ({
    modal,
    status: requireUiElement(modal, 'status', HTMLElement, 'capacity status'),
    canvas: requireUiElement(modal, 'canvas', HTMLCanvasElement, 'canvas'),
    tools: requireActionButtons(modal, CHAT_SKETCH_ACTIONS.SELECT_TOOL, 'tools'),
    swatches: requireActionButtons(modal, CHAT_SKETCH_ACTIONS.SELECT_COLOR, 'color swatches'),
    color: requireUiElement(modal, 'color', HTMLInputElement, 'color input'),
    size: requireUiElement(modal, 'size', HTMLInputElement, 'size input'),
    sizeValue: requireUiElement(modal, 'size-value', HTMLOutputElement, 'size value'),
    undo: requireUiElement(modal, 'undo', HTMLButtonElement, 'undo action'),
    redo: requireUiElement(modal, 'redo', HTMLButtonElement, 'redo action'),
    clear: requireUiElement(modal, 'clear', HTMLButtonElement, 'clear action'),
    attach: requireUiElement(modal, 'attach', HTMLButtonElement, 'attach action'),
    stage: requireUiElement(modal, 'stage', HTMLElement, 'stage'),
    grip: requireUiElement(modal, 'resize', HTMLButtonElement, 'resize grip'),
    sizePreview: requireUiElement(modal, 'size-preview', HTMLElement, 'size preview')
});

export { resolveChatSketchModalRefs };
