/* SoAI - Frontend chat sketch modal actions [frontend/assets/ts/features/chat/sketch/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const CHAT_SKETCH_ACTIONS = Object.freeze({
    SELECT_TOOL: 'sketch:select-tool',
    SELECT_COLOR: 'sketch:select-color',
    UNDO: 'sketch:undo',
    REDO: 'sketch:redo',
    CLEAR: 'sketch:clear',
    ATTACH: 'sketch:attach'
});

type ChatSketchAction = (typeof CHAT_SKETCH_ACTIONS)[keyof typeof CHAT_SKETCH_ACTIONS];

const { guard: isChatSketchAction } = createActionIdSet<ChatSketchAction>(...Object.values(CHAT_SKETCH_ACTIONS));

export { CHAT_SKETCH_ACTIONS, isChatSketchAction };
export type { ChatSketchAction };
