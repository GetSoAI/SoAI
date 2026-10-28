/* SoAI - Chat feature knowledge [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/knowledge.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';
import { buildToggleSwitchMarkup, resolveEnabledDisabledToggleLabels } from '@features/chat/modals/markup/chatconfigurationmodal/controls.ts';

const buildKnowledgeTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings, sanitizer, sectionHeader, isDetached } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;

    const enabledDisabledLabels = resolveEnabledDisabledToggleLabels();

    return `
<div id="${uiIdAttr('knowledge-content')}" class="tab-content">
  <div class="chat-config-grid">
  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rag-enabled-toggle')}" data-modal-localize="text">${strings.ragEnabled}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'rag-enabled-toggle',
        inputClassName: 'rag-enabled-toggle rag-config-input',
        checked: true,
        labels: enabledDisabledLabels
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.ragEnabledHint}</span>
  </div>

  <div class="form-group setting-change-surface chat-config-span-2">
    <div class="form-row-split${isDetached ? '' : ' form-row-split--with-action'}">
      <div class="form-col-main">
        <label for="${uiIdAttr('rag-embedding-model')}" data-modal-localize="text">${strings.ragEmbeddingModel}</label>
        ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('rag-embedding-model')}" class="form-input rag-config-input" data-modal-localize="options"></select>`)}
      </div>
      ${
          isDetached
              ? ''
              : `<div class="form-col-secondary form-col-action">
        <label>&nbsp;</label>
        <button
          type="button"
          id="${uiIdAttr('rag-download-model-btn')}"
          class="ui-button ui-variant-accent rag-download-model-btn"
          data-action="chat:goto-models-download"
          aria-label="${i18n.attr(sanitizer, 'chat.configuration.knowledge.downloadModel')}"
          data-tooltip="${i18n.attr(sanitizer, 'chat.configuration.knowledge.downloadModel')}"
         data-modal-localize="text aria-label data-tooltip">${strings.knowledgeDownloadModel}</button>
      </div>`
      }
    </div>
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.ragEmbeddingHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rag-retrieval-strategy')}" data-modal-localize="text">${strings.ragRetrievalStrategy}</label>
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('rag-retrieval-strategy')}" class="form-input rag-config-input" data-modal-localize="options">
      <option value="similarity" data-modal-localize="text">${strings.ragRetrievalSimilarity}</option>
      <option value="mmr" data-modal-localize="text">${strings.ragRetrievalMmr}</option>
      <option value="hybrid" data-modal-localize="text">${strings.ragRetrievalHybrid}</option>
    </select>`)}
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rag-top-k')}" data-modal-localize="text">${strings.ragTopK}</label>
    <input type="number" id="${uiIdAttr('rag-top-k')}" class="form-input rag-config-input" min="1" max="50" step="1">
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rag-similarity-threshold')}" data-modal-localize="text">${strings.ragSimilarityThreshold}</label>
    <input type="number" id="${uiIdAttr('rag-similarity-threshold')}" class="form-input rag-config-input" min="0" max="1" step="0.01">
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rag-chunking-strategy')}" data-modal-localize="text">${strings.ragChunkingStrategy}</label>
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('rag-chunking-strategy')}" class="form-input rag-config-input" data-modal-localize="options">
      <option value="token_based" data-modal-localize="text">${strings.ragChunkingTokenBased}</option>
      <option value="fixed_size" data-modal-localize="text">${strings.ragChunkingFixedSize}</option>
      <option value="paragraph" data-modal-localize="text">${strings.ragChunkingParagraph}</option>
      <option value="semantic" data-modal-localize="text">${strings.ragChunkingSemantic}</option>
    </select>`)}
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rag-chunk-size')}" data-modal-localize="text">${strings.ragChunkSize}</label>
    <input type="number" id="${uiIdAttr('rag-chunk-size')}" class="form-input rag-config-input" min="100" max="4000" step="1">
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rag-chunk-overlap')}" data-modal-localize="text">${strings.ragChunkOverlap}</label>
    <input type="number" id="${uiIdAttr('rag-chunk-overlap')}" class="form-input rag-config-input" min="0" max="500" step="1">
  </div>

  ${sectionHeader(strings.ragTitle)}
</div>
</div>
`;
};

export { buildKnowledgeTabMarkup };
