/* SoAI - Prompts page adapters [frontend/assets/ts/pages/prompts/controllers/page/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import { hasWebuiAction } from '@core/access/webuiPermissions.ts';
import type { SaveController } from '@core/save/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { createCardPageController, type CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import { promptsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import type { ColorToolkitHost } from '@core/ui/colorToolkitBase.ts';
import { requireContentPreviewModalService } from '@core/ui/modals/contentpreview/service.ts';
import type { PromptPreviewHost } from '@features/prompts/public.ts';
import { formatRelativeTime } from '@pages/prompts/mappers/mappers.ts';
import type { PromptEnhancerHost } from '@pages/prompts/controllers/promptenhancer/types.ts';
import { createPromptRecord, requirePromptsApi, updatePromptRecord } from '@pages/prompts/controllers/page/promptRecordManager.ts';
import type { PromptCardHost } from '@pages/prompts/rendering/CardRenderer.ts';
import type { PromptsRuntimeCore, PromptsRuntimeOwners } from '@pages/prompts/controllers/page/contracts.ts';
import type { PromptEnhancerController } from '@pages/prompts/controllers/promptenhancer/service/PromptEnhancerController.ts';

type PromptsPageAdaptersHost = PromptsRuntimeCore;

const createPromptsCardHost = (host: PromptsPageAdaptersHost, colorToolkit: import('@features/prompts/public.ts').ColorToolkit): PromptCardHost => ({
    dom: { createFragment: (html) => host.owners.dom.createFragment(html) },
    sanitizeClassName: (className, type) => host.owners.services.sanitizeClassName(className, type),
    normalizePromptColor: (value) => colorToolkit.normalize(value),
    formatDate: (timestamp) => formatRelativeTime(timestamp),
    renderColorPicker: (color, options) => colorToolkit.renderPicker(color, options)
});

const createPromptsColorToolkitHost = (owners: PromptsRuntimeOwners): ColorToolkitHost => ({
    queryUI: (selector, context) => owners.pageDom.query(selector, context),
    toggleClassName: (target, className, enabled) => owners.pageDom.toggleClass(target, className, enabled),
    optionalUI: (selector, context) => owners.pageDom.optional(selector, context),
    dom: {
        getDocument: () => owners.dom.getDocument()
    }
});

const createPromptsPromptPreviewHost = (host: PromptsPageAdaptersHost, promptEnhancer: PromptEnhancerController, save: SaveController): PromptPreviewHost => ({
    promptsApi: requirePromptsApi(host),
    findPromptById: (id) => host.operations.findPromptById(id),
    upsertPromptRecord: (record) => {
        if (!isPlainObject(record)) {
            throw new Error('Prompt preview received an invalid prompt record');
        }
        return host.operations.upsertPromptRecord(record);
    },
    requireModalElement: (id) => host.owners.services.modals.requireElement(id),
    getDocument: () => host.owners.dom.getDocument(),
    showNotification: (message, type, duration) => host.owners.feedback.show(message, type, duration),
    runTask: (name, task, options) => host.owners.streaming.runTask(name, task, options),
    notifySaveChanged: () => save.notifyChanged(),
    promptEnhancer
});

const createPromptsPromptEnhancerHost = (host: PromptsPageAdaptersHost): PromptEnhancerHost => ({
    pageDom: host.owners.pageDom,
    pageResources: host.owners.pageResources,
    feedback: host.owners.feedback,
    modals: host.owners.services.modals,
    findPromptById: (id) => host.operations.findPromptById(id),
    upsertPromptRecord: (record) => {
        const normalized = host.operations.upsertPromptRecord(record);
        if (!normalized) {
            throw new Error('Prompt enhancer failed to upsert prompt record');
        }
        return normalized;
    },
    createPrompt: async (payload) => createPromptRecord(host, { name: payload.name, content: payload.content, color: payload.color ?? null }, 'PromptEnhancer.createPrompt'),
    updatePrompt: async (id, payload) => updatePromptRecord(host, id, { name: payload.name, content: payload.content, color: payload.color ?? null }, 'PromptEnhancer.updatePrompt'),
    runTask: (name, task, options) => host.owners.streaming.runTask(name, task, options),
    fetchModelCatalog: async () => ((await hasWebuiAction('OPENAI_API')) ? host.owners.api.openai.models() : null),
    getPromptEnhancerModel: () => host.owners.storage.getPromptEnhancerModel(),
    setPromptEnhancerModel: (value) => host.owners.storage.setPromptEnhancerModel(value),
    downloadTextFile: (content, filename, mimeType) => host.operations.downloadTextFile(content, filename, mimeType),
    copyPromptContent: (content) => host.operations.copyPromptContent(content),
    buildPromptFilename: (name) => host.operations.ensureDataAdapter().buildPromptFilename(name),
    closePromptView: () => requireContentPreviewModalService().close(),
    getViewedPromptId: () => host.state.viewedPromptId
});

const createPromptsCardController = (host: PromptsPageAdaptersHost, normalizeId: (item: ResourceIncomingValue) => string | null): CardPageController =>
    createCardPageController(
        {
            dom: {
                getData: (element, key) => host.owners.dom.getData(element, key),
                setData: (element, key, value) => host.owners.dom.setData(element, key, value)
            },
            optionalUI: (selector) => host.owners.pageDom.optional(selector),
            toggleHidden: (element, hidden) => host.owners.pageElements.toggleHidden(element, hidden),
            flushDOMUpdates: () => host.owners.pageDom.flush(),
            queueResponsiveLayoutUpdate: () => host.owners.layout.queueResponsive()
        },
        {
            dataKey: promptsPageConfig.dataKey,
            itemLabel: promptsPageConfig.itemLabel,
            collectionName: promptsPageConfig.collectionName,
            cardSelector: promptsPageConfig.grid.cardSelector,
            gridSelector: promptsPageConfig.grid.gridSelector,
            cacheKey: 'prompts',
            loadingText: i18n.t('common.loading'),
            getItemId: (item: ResourceIncomingValue) => normalizeId(item),
            emptyStates: [
                { selector: promptsPageConfig.grid.emptyStateIds.empty, visibleWhen: ({ all }) => all.length === 0 },
                {
                    selector: promptsPageConfig.grid.emptyStateIds.filtered ?? 'prompts-filtered-empty',
                    visibleWhen: ({ filtered, all }) => all.length > 0 && filtered.length === 0
                }
            ]
        }
    );

export { createPromptsCardController, createPromptsCardHost, createPromptsColorToolkitHost, createPromptsPromptEnhancerHost, createPromptsPromptPreviewHost };
export type { PromptsPageAdaptersHost };
