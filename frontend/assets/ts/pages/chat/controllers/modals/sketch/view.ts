/* SoAI - Chat sketch modal view projection [frontend/assets/ts/pages/chat/controllers/modals/sketch/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import type { ChatSketchToolType } from '@features/chat/public.ts';
import type { ChatSketchModalRefs } from '@pages/chat/controllers/modals/sketch/types.ts';

type ChatSketchHistoryView = Readonly<{
    canUndo: boolean;
    canRedo: boolean;
    hasContent: boolean;
    submitting: boolean;
}>;

const projectChatSketchTool = (refs: ChatSketchModalRefs, tool: ChatSketchToolType): void => {
    for (const button of refs.tools) button.setAttribute('aria-pressed', String(button.dataset['sketchTool'] === tool));
    refs.canvas.dataset['sketchTool'] = tool;
    refs.sizePreview.dataset['sketchTool'] = tool;
};

const projectChatSketchColor = (refs: ChatSketchModalRefs, color: string): void => {
    for (const swatch of refs.swatches) swatch.setAttribute('aria-pressed', String(swatch.dataset['sketchColor'] === color));
    refs.color.value = color;
    refs.sizePreview.style.setProperty('--chat-sketch-swatch-color', color);
};

const projectChatSketchSize = (refs: ChatSketchModalRefs, size: number): void => {
    refs.size.value = String(size);
    refs.sizeValue.value = String(size);
    refs.sizePreview.style.setProperty('--chat-sketch-size', `${String(size)}px`);
};

const projectChatSketchHistory = (refs: ChatSketchModalRefs, view: ChatSketchHistoryView): void => {
    setControlDisabledState(refs.undo, view.submitting || !view.canUndo);
    setControlDisabledState(refs.redo, view.submitting || !view.canRedo);
    setControlDisabledState(refs.clear, view.submitting || !view.hasContent);
    if (!view.submitting) setControlDisabledState(refs.attach, !view.hasContent);
};

export { projectChatSketchColor, projectChatSketchHistory, projectChatSketchSize, projectChatSketchTool };
