/* SoAI - Chat page memorytab service [frontend/assets/ts/pages/chat/widgets/memorytab/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import type { ChatMemoryEntry, ChatMemorySnapshot } from '@core/api/contracts/webuiMemoryContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { escapeHtml } from '@core/security/textSanitizer.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ChatMemoryTabHost extends PageDomOwnerHost {
    isCurrent(): boolean;
    api: {
        webui?: {
            memory?: {
                get?: () => Promise<ChatMemorySnapshot>;
            };
        };
    };
}

const buildObservationMarkup = (observation: ChatMemoryEntry['observations'][number]): string => {
    const { content } = observation;
    const source = observation.source ?? '';
    const sourceMarkup = source ? `<span class="chat-memory-source">${escapeHtml(source)}</span>` : '';
    return `<li class="chat-memory-list-item"><span class="chat-memory-content">${escapeHtml(content)}</span>${sourceMarkup}</li>`;
};

const buildRelationMarkup = (relation: ChatMemoryEntry['relations'][number]): string => {
    const { relationType } = relation;
    const target = relation.toEntity ?? relation.fromEntity;
    if (target === null) {
        throw new Error('Chat memory relation must identify a related entity');
    }
    return `<li class="chat-memory-list-item"><span class="chat-memory-content">${escapeHtml(relationType)}: ${escapeHtml(target)}</span></li>`;
};

const buildEntryMarkup = (entry: ChatMemoryEntry): string => {
    const { name, entityType } = entry.entity;
    const { observations, relations } = entry;
    const observationMarkup = observations.map((observation) => buildObservationMarkup(observation)).join('');
    const relationMarkup = relations.map((relation) => buildRelationMarkup(relation)).join('');
    const observationsLabel = escapeHtml(i18n.t('chat.memory.viewer.observations'));
    const relationsLabel = escapeHtml(i18n.t('chat.memory.viewer.relations'));
    const noneLabel = escapeHtml(i18n.t('chat.memory.viewer.none'));
    return `<section class="chat-memory-entry"><header class="chat-memory-entry-header"><h3>${escapeHtml(name)}</h3><span class="chat-memory-entry-type">${escapeHtml(entityType)}</span></header><div class="chat-memory-entry-section"><h4>${observationsLabel}</h4><ul class="chat-memory-list">${observationMarkup || `<li class="chat-memory-list-item">${noneLabel}</li>`}</ul></div><div class="chat-memory-entry-section"><h4>${relationsLabel}</h4><ul class="chat-memory-list">${relationMarkup || `<li class="chat-memory-list-item">${noneLabel}</li>`}</ul></div></section>`;
};

const sortMemoryEntries = (entries: ChatMemoryEntry[]): ChatMemoryEntry[] => {
    return [...entries].sort((left, right) => {
        return right.entity.updatedAtMs - left.entity.updatedAtMs;
    });
};

const refreshChatMemoryTab = async (host: ChatMemoryTabHost, modalRoot: HTMLElement): Promise<void> => {
    const memoryApi = host.api.webui?.memory;
    if (!memoryApi?.get) {
        throw new Error('Chat memory tab requires api.webui.memory.get');
    }
    const viewer = host.pageDom.requireHTMLElement(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'memory-viewer'), modalRoot);
    const empty = host.pageDom.requireHTMLElement(modalUiSelector(CHAT_CONFIGURATION_MODAL_ID, 'memory-empty'), modalRoot);
    const response = await memoryApi.get();
    const entries = sortMemoryEntries(response.entries);
    if (!host.isCurrent()) {
        return;
    }
    if (entries.length === 0) {
        const emptyMarkup = EMPTY_UI_HTML;
        host.pageDom.updateHtml(viewer, emptyMarkup);
        host.pageDom.toggleClass(empty, 'u-hidden', false);
        return;
    }
    host.pageDom.toggleClass(empty, 'u-hidden', true);
    const markup = entries.map((entry) => buildEntryMarkup(entry)).join('');
    const trustedMarkup = toTrustedUiHtml(markup);
    host.pageDom.updateHtml(viewer, trustedMarkup);
};

export { refreshChatMemoryTab };
export type { ChatMemoryTabHost };
