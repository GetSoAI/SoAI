/* SoAI - Shared route registry constants [frontend/assets/ts/core/routeregistry/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { CAPS, HARDWARE, LOGS_CORE, METRICS, MODELS, PLUGINS, PROMPTS, STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import type { RawRouteDefinition } from '@core/routeregistry/contracts.ts';
import { resolveRouteSearchMetadata } from '@core/routeregistry/searchMetadata.ts';

const MOVABLE_LAYOUT_HEADER_ACTION_HANDOFF: readonly string[] = [HEADER_ACTION_IDS.edit];

const ROUTE_DEFINITIONS_RAW: RawRouteDefinition[] = [
    {
        id: 'dashboard',
        path: 'dashboard',
        component: 'dashboard',
        getTitle: () => i18n.t('pages.dashboard.title'),
        auth: true,
        actions: ['SYSTEM_STATUS_READ'],
        data: { streams: [STATUS] },
        layout: { headerActionHandoff: MOVABLE_LAYOUT_HEADER_ACTION_HANDOFF },
        search: resolveRouteSearchMetadata('dashboard'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.dashboard'), icon: 'dashboard', section: null, order: 10 }
    },
    {
        id: 'chat',
        path: 'chat',
        component: 'chat',
        getTitle: () => i18n.t('pages.chat.title'),
        auth: true,
        data: { streams: [MODELS] },
        search: resolveRouteSearchMetadata('chat'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.chat'), icon: 'chat', section: null, order: 20 }
    },
    {
        id: 'chatConversation',
        path: 'chat/conversation/:conversationId',
        component: 'chat',
        getTitle: () => i18n.t('pages.chat.title'),
        auth: true,
        data: { streams: [MODELS] },
        sidebar: { include: false, parent: 'chat' }
    },
    {
        id: 'automation',
        path: 'automation',
        component: 'automation',
        getTitle: () => i18n.t('pages.automation.title'),
        auth: true,
        data: { streams: [MODELS] },
        sidebar: { include: true, getLabel: () => i18n.t('nav.automation'), icon: 'automation', section: null, order: 25 }
    },
    {
        id: 'prompts',
        path: 'prompts',
        component: 'prompts',
        getTitle: () => i18n.t('pages.prompts.title'),
        auth: true,
        data: { streams: [PROMPTS] },
        sidebar: { include: true, getLabel: () => i18n.t('nav.prompts'), icon: 'prompt', section: 'management', order: 30 }
    },
    {
        id: 'plugins',
        path: 'plugins',
        component: 'plugins',
        getTitle: () => i18n.t('pages.plugins.title'),
        auth: true,
        actions: ['PLUGIN_READ'],
        data: { streams: [PLUGINS, CAPS] },
        search: resolveRouteSearchMetadata('plugins'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.plugins'), icon: 'plugin', section: 'management', order: 40 }
    },
    {
        id: 'models',
        path: 'models',
        component: 'models',
        getTitle: () => i18n.t('pages.models.title'),
        auth: true,
        actions: ['MODEL_READ'],
        data: { streams: [MODELS] },
        search: resolveRouteSearchMetadata('models'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.models'), icon: 'model-default', section: 'management', order: 50 }
    },
    {
        id: 'hardware',
        path: 'hardware',
        component: 'hardware',
        getTitle: () => i18n.t('pages.hardware.title'),
        auth: true,
        actions: ['HARDWARE_READ'],
        data: { streams: [HARDWARE] },
        layout: { headerActionHandoff: MOVABLE_LAYOUT_HEADER_ACTION_HANDOFF },
        search: resolveRouteSearchMetadata('hardware'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.hardware'), icon: 'hardware', section: 'management', order: 60 }
    },
    {
        id: 'metrics',
        path: 'metrics',
        component: 'metrics',
        getTitle: () => i18n.t('pages.metrics.title'),
        auth: true,
        data: { streams: [METRICS] },
        layout: { headerActionHandoff: MOVABLE_LAYOUT_HEADER_ACTION_HANDOFF },
        search: resolveRouteSearchMetadata('metrics'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.metrics'), icon: 'metrics', section: 'analytics', order: 70 }
    },
    {
        id: 'power',
        path: 'power',
        component: 'power',
        getTitle: () => i18n.t('pages.power.title'),
        auth: true,
        adminOnly: true,
        actions: ['SYSTEM_POWER'],
        data: { streams: [] },
        search: resolveRouteSearchMetadata('power'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.power'), icon: 'power', section: 'system', order: 115, adminOnly: true }
    },
    {
        id: 'terminal',
        path: 'terminal',
        component: 'terminal',
        getTitle: () => i18n.t('pages.terminal.title'),
        auth: true,
        actions: ['TERMINAL_USE'],
        data: { streams: [] },
        sidebar: { include: true, getLabel: () => i18n.t('nav.terminal'), icon: 'terminal', section: 'system', order: 90 }
    },
    {
        id: 'fileExplorer',
        path: 'fileExplorer',
        component: 'fileExplorer',
        getTitle: () => i18n.t('pages.fileExplorer.title'),
        auth: true,
        actions: ['FILE_EXPLORER_READ'],
        data: { streams: [] },
        search: resolveRouteSearchMetadata('fileExplorer'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.fileExplorer'), icon: 'folder', section: 'system', order: 102 }
    },
    {
        id: 'help',
        path: 'help',
        component: 'help',
        getTitle: () => i18n.t('pages.help.title'),
        auth: true,
        data: { streams: [] },
        search: resolveRouteSearchMetadata('help'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.help'), icon: 'help', section: 'system', order: 116 }
    },
    {
        id: 'logs',
        path: 'logs',
        component: 'logs',
        getTitle: () => i18n.t('pages.logs.title'),
        auth: true,
        actions: ['LOG_ACCESS'],
        data: { streams: [LOGS_CORE] },
        sidebar: {
            include: true,
            getLabel: () => i18n.t('pages.logs.title'),
            icon: 'logs',
            section: 'system',
            order: 117,
            parent: null
        }
    },
    {
        id: 'settings',
        path: 'settings',
        component: 'settings',
        getTitle: () => i18n.t('pages.settings.title'),
        auth: true,
        data: { streams: [] },
        search: resolveRouteSearchMetadata('settings'),
        sidebar: {
            include: true,
            getLabel: () => i18n.t('nav.settings'),
            icon: 'settings',
            section: 'system',
            order: 114,
            parent: null
        }
    },
    {
        id: 'updates',
        path: 'updates',
        component: 'updates',
        getTitle: () => i18n.t('pages.updates.title'),
        auth: true,
        actions: ['SOFTWARE_UPDATE'],
        data: { streams: [] },
        search: resolveRouteSearchMetadata('updates'),
        sidebar: { include: false, parent: null }
    },
    {
        id: 'about',
        path: 'about',
        component: 'about',
        getTitle: () => i18n.t('pages.about.title'),
        auth: true,
        actions: ['SYSTEM_STATUS_READ', 'HARDWARE_READ'],
        data: { streams: [] },
        search: resolveRouteSearchMetadata('about'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.about'), icon: 'info', section: 'system', order: 125, parent: null }
    },
    {
        id: 'search',
        path: 'search',
        component: 'search',
        getTitle: () => i18n.t('pages.search.title'),
        auth: true,
        data: { streams: [] },
        sidebar: { include: false, parent: null }
    },
    {
        id: 'forbidden',
        path: 'forbidden',
        component: 'forbidden',
        getTitle: () => i18n.t('pages.forbidden.title'),
        auth: true,
        data: { streams: [] },
        sidebar: { include: false, parent: null }
    },
    {
        id: 'login',
        path: 'login',
        component: 'login',
        getTitle: () => i18n.t('pages.login.title'),
        auth: false,
        data: { streams: [] },
        sidebar: { include: false, parent: null },
        layout: { hideSidebar: true }
    },
    {
        id: 'wizard',
        path: 'wizard',
        component: 'wizard',
        getTitle: () => i18n.t('pages.wizard.title'),
        auth: false,
        data: { streams: [] },
        sidebar: { include: false, parent: null },
        layout: { hideSidebar: true }
    },
    {
        id: 'modelDetail',
        path: 'model/:id',
        component: 'modelDetail',
        getTitle: () => i18n.t('pages.modelDetail.title'),
        auth: true,
        data: { streams: [MODELS, PLUGINS] },
        sidebar: { include: false, parent: 'models' },
        layout: { scrollToTopAction: false }
    }
];

export { ROUTE_DEFINITIONS_RAW };
