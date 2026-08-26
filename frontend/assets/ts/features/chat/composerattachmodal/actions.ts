/* SoAI - Chat composer attach modal action IDs [frontend/assets/ts/features/chat/composerattachmodal/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const CHAT_ATTACH_MODAL_ACTIONS = Object.freeze({
    CHOOSE_UPLOAD: 'chat-attach-modal:choose-upload',
    CHOOSE_KNOWLEDGE_UPLOAD: 'chat-attach-modal:choose-knowledge-upload',
    CHOOSE_FILE: 'chat-attach-modal:choose-file',
    CHOOSE_FOLDER: 'chat-attach-modal:choose-folder',
    CAMERA_SHUTTER: 'chat-attach-modal:camera-shutter',
    CAMERA_RETAKE: 'chat-attach-modal:camera-retake',
    CAMERA_USE: 'chat-attach-modal:camera-use',
    CAMERA_FLIP: 'chat-attach-modal:camera-flip',
    BROWSE_SELECT: 'chat-attach-modal:browse-select',
    BROWSE_OPEN: 'chat-attach-modal:browse-open',
    BROWSE_SORT: 'chat-attach-modal:browse-sort',
    BROWSE_CHANGE_WORKSPACE_PATH: 'chat-attach-modal:browse-change-workspace-path',
    BROWSE_PREVIEW: 'chat-attach-modal:browse-preview',
    BROWSE_ATTACH: 'chat-attach-modal:browse-attach',
    KNOWLEDGE_IMPORT: 'chat-attach-modal:knowledge-import',
    KNOWLEDGE_REINDEX: 'chat-attach-modal:knowledge-reindex',
    ATTACH_FOLDER: 'chat-attach-modal:attach-folder',
    ATTACH_DOCUMENTS: 'chat-attach-modal:attach-documents'
});

type ChatAttachModalAction = (typeof CHAT_ATTACH_MODAL_ACTIONS)[keyof typeof CHAT_ATTACH_MODAL_ACTIONS];

const { guard: isChatAttachModalAction } = createActionIdSet<ChatAttachModalAction>(...Object.values(CHAT_ATTACH_MODAL_ACTIONS));

export { CHAT_ATTACH_MODAL_ACTIONS, isChatAttachModalAction };
export type { ChatAttachModalAction };
