/* SoAI - Chat composer attach modal action IDs [frontend/assets/ts/features/attachmodal/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';

const ATTACH_MODAL_ACTIONS = Object.freeze({
    CHOOSE_UPLOAD: 'chat-attach-modal:choose-upload',
    CHOOSE_KNOWLEDGE_UPLOAD: 'chat-attach-modal:choose-knowledge-upload',
    CHOOSE_FILE: 'chat-attach-modal:choose-file',
    CHOOSE_FOLDER: 'chat-attach-modal:choose-folder',
    CAMERA_SHUTTER: 'chat-attach-modal:camera-shutter',
    CAMERA_RETAKE: 'chat-attach-modal:camera-retake',
    CAMERA_USE: 'chat-attach-modal:camera-use',
    CAMERA_SWITCH: 'chat-attach-modal:camera-switch',
    BROWSE_SELECT: 'chat-attach-modal:browse-select',
    BROWSE_OPEN: 'chat-attach-modal:browse-open',
    BROWSE_SORT: 'chat-attach-modal:browse-sort',
    BROWSE_CHANGE_WORKSPACE_PATH: 'chat-attach-modal:browse-change-workspace-path',
    BROWSE_PREVIEW: 'chat-attach-modal:browse-preview',
    BROWSE_ATTACH: 'chat-attach-modal:browse-attach',
    KNOWLEDGE_IMPORT: 'chat-attach-modal:knowledge-import',
    KNOWLEDGE_REINDEX: 'chat-attach-modal:knowledge-reindex',
    REMOVE_ALL: 'chat-attach-modal:remove-all',
    ATTACH_FOLDER: 'chat-attach-modal:attach-folder',
    ATTACH_DOCUMENTS: 'chat-attach-modal:attach-documents'
});

type AttachModalAction = (typeof ATTACH_MODAL_ACTIONS)[keyof typeof ATTACH_MODAL_ACTIONS];

const { guard: isAttachModalAction } = createActionIdSet<AttachModalAction>(...Object.values(ATTACH_MODAL_ACTIONS));

export { ATTACH_MODAL_ACTIONS, isAttachModalAction };
export type { AttachModalAction };
