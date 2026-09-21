/* SoAI - Chat composer attach modal definition [frontend/assets/ts/features/chat/composerattachmodal/definition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildWorkspaceFolderFieldMarkup } from '@core/fileexplorerbrowser/workspaceFolderFieldMarkup.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { MODAL_HEADER_CLOSE_SELECTOR } from '@core/modals/headerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { EMPTY_UI_HTML, staticUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderSearchFieldActions } from '@core/ui/searchField.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { CHAT_ATTACH_MODAL_ACTIONS } from '@features/chat/composerattachmodal/actions.ts';
import { CHAT_ATTACH_MODAL_ID } from '@features/chat/modals/constants.ts';

const renderAttachModalTabs = () => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    return uiHtml`<div id="${uiAttr(modalUiId(modalId, 'tabs'))}" class="chat-attach-modal-tabs"></div>`;
};

const renderTabHeader = (title: string, subtitle: string) => uiHtml`<div class="form-group chat-attach-modal-tab-header"><label>${title}</label><span class="chat-attach-modal-tab-subtitle">${subtitle}</span></div>`;

const renderUnifiedDropzoneIcons = () => {
    const icons: IconName[] = ['file-generic', 'file-image', 'file-audio', 'file-video', 'code', 'folder', 'folder-archive'];
    return toTrustedUiHtml(icons.map((iconName) => `<span class="chat-attach-modal-unified-icon" aria-hidden="true">${getIconSync(iconName, { size: 20, strokeWidth: 1.5 }).html}</span>`).join(''));
};

const renderUnifiedAttachDropzone = (token: string, action: string, title: string, hint: string) => {
    return uiHtml`<button id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, token))}" class="chat-attach-modal-dropzone chat-attach-modal-dropzone-unified" type="button" aria-label="${uiAttr(title)}" data-tooltip="${uiAttr(title)}" data-action="${uiAttr(action)}">
        <span class="chat-attach-modal-unified-icons">${renderUnifiedDropzoneIcons()}</span>
        <span class="chat-attach-modal-dropzone-copy">
            <strong class="chat-attach-modal-dropzone-title">${title}</strong>
            <span class="chat-attach-modal-hint">${hint}</span>
        </span>
    </button>`;
};

const renderAttachActionButton = (token: string, action: string, label: string) => {
    return uiHtml`<button id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, token))}" class="ui-button ui-variant-neutral chat-attach-modal-action-button" type="button" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" data-action="${uiAttr(action)}">${label}</button>`;
};

const renderAttachActionRow = (buttons: readonly string[]) => {
    return toTrustedUiHtml(buttons.join(''));
};

const renderRemoveAllButton = (tokenPrefix: string) => {
    const label = i18n.t('chat.attachModal.removeAll');
    return uiHtml`<button id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, `${tokenPrefix}-remove-all`))}" class="ui-button ui-variant-danger chat-attach-modal-action-button" type="button" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" data-action="${uiAttr(CHAT_ATTACH_MODAL_ACTIONS.REMOVE_ALL)}" disabled aria-disabled="true" hidden>${label}</button>`;
};

const renderDraftAttachmentStatus = (tokenPrefix: string) => uiHtml`<div id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, `${tokenPrefix}-status`))}" class="chat-configuration-hint u-hidden inline-loading-status chat-attach-draft-attachment-status"></div>`;

const renderDraftAttachmentCollection = (tokenPrefix: string) => uiHtml`<div id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, `${tokenPrefix}-summary`))}" class="chat-configuration-hint u-hidden chat-attach-draft-attachment-summary"></div><div id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, `${tokenPrefix}-list`))}" class="chat-attach-draft-attachment-list u-hidden"></div>`;

const renderUploadPane = () => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    return uiHtml`<section id="${uiAttr(modalUiId(modalId, 'pane-upload'))}" class="chat-attach-modal-pane is-active" role="tabpanel" aria-labelledby="${uiAttr(modalUiId(modalId, 'tab-upload'))}">
        ${renderTabHeader(i18n.t('chat.attachModal.uploadTitle'), i18n.t('chat.attachModal.uploadSubtitle'))}
        ${renderDraftAttachmentStatus('upload')}
        ${renderUnifiedAttachDropzone('dropzone', CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_UPLOAD, i18n.t('chat.attachModal.uploadDropTitle'), i18n.t('chat.attachModal.dropzoneHint'))}
        <div class="chat-attach-modal-actions">
            ${renderAttachActionRow([renderAttachActionButton('upload-file-button', CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_FILE, i18n.t('chat.attachModal.uploadFileButton')).html, renderAttachActionButton('upload-folder-button', CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_FOLDER, i18n.t('chat.attachModal.uploadFolderButton')).html, renderRemoveAllButton('upload').html])}
        </div>
        ${renderDraftAttachmentCollection('upload')}
    </section>`;
};

const renderCameraStage = () => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    return uiHtml`<div id="${uiAttr(modalUiId(modalId, 'camera-stage'))}" class="chat-attach-modal-camera-stage">
        <video id="${uiAttr(modalUiId(modalId, 'camera-video'))}" class="chat-attach-modal-camera-video" autoplay playsinline muted></video>
        <canvas id="${uiAttr(modalUiId(modalId, 'camera-canvas'))}" class="chat-attach-modal-camera-canvas" hidden></canvas>
        <div id="${uiAttr(modalUiId(modalId, 'camera-status'))}" class="chat-attach-modal-camera-status" aria-live="polite">${i18n.t('chat.attachModal.cameraPreparing')}</div>
    </div>`;
};

const renderCameraButton = (token: string, action: string, label: string, iconName: IconName, className = '') => {
    const classNames = className ? `chat-attach-camera-control chat-attach-camera-control-${token} ${className}` : `chat-attach-camera-control chat-attach-camera-control-${token}`;
    return uiHtml`<button id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, token))}" class="${uiAttr(classNames)}" type="button" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" data-action="${uiAttr(action)}"><span class="chat-attach-camera-control-icon" aria-hidden="true">${getIconSync(iconName, { size: 18, strokeWidth: 2 })}</span><span class="visually-hidden">${label}</span></button>`;
};

const renderCameraShutterButton = () => {
    const label = i18n.t('chat.attachModal.cameraShutter');
    return uiHtml`<button id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, 'camera-shutter'))}" class="chat-attach-camera-control chat-attach-camera-control-camera-shutter chat-attach-camera-shutter" type="button" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" data-action="${uiAttr(CHAT_ATTACH_MODAL_ACTIONS.CAMERA_SHUTTER)}"><span class="chat-attach-camera-shutter-core" aria-hidden="true"></span><span class="visually-hidden">${label}</span></button>`;
};

const renderCameraPane = () => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    return uiHtml`<section id="${uiAttr(modalUiId(modalId, 'pane-camera'))}" class="chat-attach-modal-pane chat-attach-modal-camera" role="tabpanel" aria-labelledby="${uiAttr(modalUiId(modalId, 'tab-camera'))}" hidden aria-hidden="true">
        ${renderTabHeader(i18n.t('chat.attachModal.cameraTitle'), i18n.t('chat.attachModal.cameraSubtitle'))}
        ${renderCameraStage()}
        <div class="chat-attach-modal-camera-controls">
            <div class="chat-attach-modal-camera-control-row">
                ${renderCameraButton('camera-switch', CHAT_ATTACH_MODAL_ACTIONS.CAMERA_SWITCH, i18n.t('chat.attachModal.cameraSwitch'), 'camera')}
                ${renderCameraShutterButton()}
                ${renderCameraButton('camera-retake', CHAT_ATTACH_MODAL_ACTIONS.CAMERA_RETAKE, i18n.t('chat.attachModal.cameraRetake'), 'refresh')}
                ${renderCameraButton('camera-use', CHAT_ATTACH_MODAL_ACTIONS.CAMERA_USE, i18n.t('chat.attachModal.cameraUse'), 'check')}
            </div>
        </div>
        <div class="chat-attach-modal-camera-drafts">${renderDraftAttachmentStatus('camera')}${renderDraftAttachmentCollection('camera')}<div class="chat-attach-modal-actions">${renderRemoveAllButton('camera')}</div></div>
    </section>`;
};

const renderBrowsePane = () => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    const searchLabel = i18n.t('chat.attachModal.searchLabel');
    const workspaceField = buildWorkspaceFolderFieldMarkup({
        pathInputId: modalUiId(modalId, 'browse-workspace-path'),
        changeButtonId: modalUiId(modalId, 'browse-workspace-change-btn'),
        label: i18n.t('chat.configuration.filesFolder.currentLabel'),
        buttonLabel: i18n.t('chat.configuration.filesFolder.changeButton'),
        action: CHAT_ATTACH_MODAL_ACTIONS.BROWSE_CHANGE_WORKSPACE_PATH,
        changeSurface: false,
        status: false,
        fieldClassName: 'chat-attach-folder-field',
        rowClassName: 'chat-attach-folder-row',
        mainClassName: 'chat-attach-folder-main',
        actionClassName: 'chat-attach-folder-action'
    });
    return uiHtml`<section id="${uiAttr(modalUiId(modalId, 'pane-browse'))}" class="chat-attach-modal-pane" role="tabpanel" aria-labelledby="${uiAttr(modalUiId(modalId, 'tab-browse'))}" hidden aria-hidden="true">
        ${renderTabHeader(i18n.t('chat.attachModal.browseTitle'), i18n.t('chat.attachModal.browseSubtitle'))}
        <div class="chat-config-grid">
            ${workspaceField}
        </div>
        <div class="searchbar-container searchbar-container--collection chat-attach-modal-search">
            <input id="${uiAttr(modalUiId(modalId, 'search'))}" class="searchbar-input" type="search" aria-label="${uiAttr(searchLabel)}" placeholder="${uiAttr(i18n.t('chat.attachModal.searchPlaceholder'))}">
            ${renderSearchFieldActions()}
        </div>
        <div id="${uiAttr(modalUiId(modalId, 'results'))}" class="chat-attach-modal-results" aria-live="polite">
            <div class="chat-attach-empty-state">
                <span class="chat-attach-empty-state-icon" aria-hidden="true">${getIconSync('file-database', { size: 26, strokeWidth: 1.5 })}</span>
                <strong class="chat-attach-empty-state-title">${i18n.t('chat.attachModal.browseEmptyTitle')}</strong>
                <p class="chat-attach-modal-hint">${i18n.t('chat.attachModal.browseEmptySubtitle')}</p>
            </div>
        </div>
        ${renderDraftAttachmentStatus('browse')}
        ${renderDraftAttachmentCollection('browse')}
        <div class="chat-attach-modal-actions">${renderRemoveAllButton('browse')}</div>
    </section>`;
};

const renderSoaiLinkPane = () => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    const inputLabel = i18n.t('chat.attachModal.soaiLinkInputLabel');
    return uiHtml`<section id="${uiAttr(modalUiId(modalId, 'pane-soai-link'))}" class="chat-attach-modal-pane chat-attach-modal-soai-link" role="tabpanel" aria-labelledby="${uiAttr(modalUiId(modalId, 'tab-soai-link'))}" hidden aria-hidden="true">
        ${renderTabHeader(i18n.t('chat.attachModal.soaiLinkTitle'), i18n.t('chat.attachModal.soaiLinkSubtitle'))}
        ${renderDraftAttachmentStatus('soai-link')}
        <label class="visually-hidden" for="${uiAttr(modalUiId(modalId, 'soai-link-input'))}">${inputLabel}</label>
        <textarea id="${uiAttr(modalUiId(modalId, 'soai-link-input'))}" class="chat-attach-modal-soai-link-input" aria-label="${uiAttr(inputLabel)}" placeholder="${uiAttr(i18n.t('chat.attachModal.soaiLinkPlaceholder'))}" rows="5"></textarea>
        ${renderDraftAttachmentCollection('soai-link')}
        <div class="chat-attach-modal-actions">${renderRemoveAllButton('soai-link')}</div>
    </section>`;
};

const renderKnowledgeSecondaryAction = (token: string, action: string, label: string, disabled = false, initiallyHidden = false) => {
    const disabledAttrs = disabled ? staticUiHtml`disabled aria-disabled="true"` : EMPTY_UI_HTML;
    const hiddenAttr = initiallyHidden ? staticUiHtml`hidden` : EMPTY_UI_HTML;
    return uiHtml`<button id="${uiAttr(modalUiId(CHAT_ATTACH_MODAL_ID, token))}" class="ui-button ui-variant-neutral chat-attach-modal-action-button" type="button" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" data-action="${uiAttr(action)}" ${disabledAttrs} ${hiddenAttr}>${label}</button>`;
};

const renderKnowledgePane = () => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    return uiHtml`<section id="${uiAttr(modalUiId(modalId, 'pane-knowledge'))}" class="chat-attach-modal-pane chat-attach-modal-knowledge" role="tabpanel" aria-labelledby="${uiAttr(modalUiId(modalId, 'tab-knowledge'))}" hidden aria-hidden="true">
        ${renderTabHeader(i18n.t('chat.attachModal.knowledgeTitle'), i18n.t('chat.attachModal.knowledgeSubtitle'))}
        <input type="file" id="${uiAttr(modalUiId(modalId, 'knowledge-document-input'))}" class="u-hidden chat-attach-knowledge-document-input" multiple>
        <input type="file" id="${uiAttr(modalUiId(modalId, 'knowledge-folder-input'))}" class="u-hidden chat-attach-knowledge-folder-input" webkitdirectory directory multiple>
        ${renderUnifiedAttachDropzone('knowledge-dropzone', CHAT_ATTACH_MODAL_ACTIONS.CHOOSE_KNOWLEDGE_UPLOAD, i18n.t('chat.attachModal.knowledgeDropTitle'), i18n.t('chat.attachModal.knowledgeDropHint'))}
        <div class="chat-attach-modal-actions">
            ${renderAttachActionRow([renderAttachActionButton('knowledge-file-button', CHAT_ATTACH_MODAL_ACTIONS.ATTACH_DOCUMENTS, i18n.t('chat.attachModal.uploadFileButton')).html, renderAttachActionButton('knowledge-folder-button', CHAT_ATTACH_MODAL_ACTIONS.ATTACH_FOLDER, i18n.t('chat.attachModal.uploadFolderButton')).html, renderKnowledgeSecondaryAction('knowledge-import', CHAT_ATTACH_MODAL_ACTIONS.KNOWLEDGE_IMPORT, i18n.t('chat.attachModal.knowledgeImportButton')).html, renderKnowledgeSecondaryAction('knowledge-reindex', CHAT_ATTACH_MODAL_ACTIONS.KNOWLEDGE_REINDEX, i18n.t('chat.configuration.knowledge.reindex'), true, true).html, renderRemoveAllButton('knowledge').html])}
        </div>
        <div id="${uiAttr(modalUiId(modalId, 'knowledge-progress'))}" class="rag-upload-progress chat-attach-knowledge-progress"></div>
        <div id="${uiAttr(modalUiId(modalId, 'knowledge-summary'))}" class="chat-configuration-hint rag-documents-summary u-hidden inline-loading-status chat-attach-knowledge-summary"></div>
        <div id="${uiAttr(modalUiId(modalId, 'knowledge-documents-list'))}" class="rag-documents-list chat-attach-knowledge-documents-list"></div>
    </section>`;
};

const renderAttachModalBody = () => {
    return uiHtml`<div class="chat-attach-modal-body">${renderUploadPane()}${renderCameraPane()}${renderBrowsePane()}${renderSoaiLinkPane()}${renderKnowledgePane()}</div>`;
};

const renderAttachModalFooterActions = () => {
    return toTrustedUiHtml([renderModalFooterActionButton({ id: modalUiId(CHAT_ATTACH_MODAL_ID, 'browse-preview'), action: CHAT_ATTACH_MODAL_ACTIONS.BROWSE_PREVIEW, text: i18n.t('chat.attachModal.browsePreview'), disabled: true, attributes: { hidden: true } }), renderModalFooterActionButton({ id: modalUiId(CHAT_ATTACH_MODAL_ID, 'browse-attach'), action: CHAT_ATTACH_MODAL_ACTIONS.BROWSE_ATTACH, text: i18n.t('chat.attachModal.browseAttach'), variant: 'primary', disabled: true, attributes: { hidden: true } })].map((button) => button.html).join(''));
};

const createChatAttachModalDefinition = (): ModalDefinition => {
    const modalId = CHAT_ATTACH_MODAL_ID;
    return {
        id: modalId,
        layout: 'xl',
        initialFocusSelector: MODAL_HEADER_CLOSE_SELECTOR,
        createElement: (_options: ModalOpenOptions): HTMLElement => {
            const titleId = modalUiId(modalId, 'title');
            const closeLabel = i18n.t('common.close');
            const header = renderStandardModalHeader({
                modalId,
                title: i18n.t('chat.attachModal.title'),
                description: i18n.t('common.modalDescriptions.chatAttach'),
                closeLabel,
                titleId,
                sections: renderAttachModalTabs()
            });
            const body = renderModalBody(renderAttachModalBody());
            const footer = renderSplitModalFooter({
                left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
                right: renderAttachModalFooterActions(),
                className: 'chat-attach-modal-footer'
            });
            return createModalElement({
                id: modalId,
                rootAttributes: { 'data-page-scope': 'chat' },
                header,
                body,
                footer
            });
        }
    };
};

export { createChatAttachModalDefinition };
