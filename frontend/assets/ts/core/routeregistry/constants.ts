/* SoAI - Shared route registry constants [frontend/assets/ts/core/routeregistry/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import { CAPS, HARDWARE, LOGS_CORE, METRICS, MODELS, PLUGINS, PROMPTS, STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import type { RawRouteDefinition } from '@core/routeregistry/contracts.ts';
import { resolveRouteSearchMetadata } from '@core/routeregistry/searchMetadata.ts';
import { INITIAL_MODAL_QUERY_KEYS, AUTOMATION_RECONSTRUCTION_QUERY_KEYS, PLUGINS_INITIAL_MODAL_QUERY_KEYS, MODELS_INITIAL_ACTION_QUERY_KEYS, READ_ROUTE_RECONSTRUCTION, CLEAN_READ_ROUTE_RECONSTRUCTION } from '@core/routeregistry/reconstruction.ts';

const MOVABLE_LAYOUT_HEADER_ACTION_HANDOFF: readonly string[] = [HEADER_ACTION_IDS.edit];

const ROUTE_DEFINITIONS_RAW: RawRouteDefinition[] = [
    {
        id: 'dashboard',
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        reconstruction: { discardQuery: INITIAL_MODAL_QUERY_KEYS },
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
        reconstruction: { discardQuery: INITIAL_MODAL_QUERY_KEYS },
        path: 'chat/conversation/:conversationId',
        component: 'chat',
        getTitle: () => i18n.t('pages.chat.title'),
        auth: true,
        data: { streams: [MODELS] },
        sidebar: { include: false, parent: 'chat' }
    },
    {
        id: 'automation',
        reconstruction: { discardQuery: AUTOMATION_RECONSTRUCTION_QUERY_KEYS },
        path: 'automation',
        component: 'automation',
        getTitle: () => i18n.t('pages.automation.title'),
        auth: true,
        data: { streams: [MODELS] },
        sidebar: { include: true, getLabel: () => i18n.t('nav.automation'), icon: 'automation', section: null, order: 25 }
    },
    {
        id: 'prompts',
        reconstruction: READ_ROUTE_RECONSTRUCTION,
        path: 'prompts',
        component: 'prompts',
        getTitle: () => i18n.t('pages.prompts.title'),
        auth: true,
        data: { streams: [PROMPTS] },
        sidebar: { include: true, getLabel: () => i18n.t('nav.prompts'), icon: 'prompt', section: 'management', order: 30 }
    },
    {
        id: 'plugins',
        reconstruction: { discardQuery: PLUGINS_INITIAL_MODAL_QUERY_KEYS, whenQuery: 'modal' },
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
        reconstruction: { discardQuery: MODELS_INITIAL_ACTION_QUERY_KEYS, whenQuery: 'action' },
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
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        sidebar: { include: true, activateOnNavigation: false, getLabel: () => i18n.t('nav.power'), icon: 'power', section: 'system', order: 115, adminOnly: true }
    },
    {
        id: 'terminal',
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        reconstruction: CLEAN_READ_ROUTE_RECONSTRUCTION,
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
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        reconstruction: { discardQuery: INITIAL_MODAL_QUERY_KEYS },
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
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        layout: { exclusive: true },
        actions: ['SYSTEM_STATUS_READ', 'HARDWARE_READ'],
        data: { streams: [] },
        search: resolveRouteSearchMetadata('about'),
        sidebar: { include: true, getLabel: () => i18n.t('nav.about'), icon: 'info', section: 'system', order: 125, parent: null }
    },
    {
        id: 'search',
        reconstruction: READ_ROUTE_RECONSTRUCTION,
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
        layout: { hideSidebar: true, exclusive: true }
    },
    {
        id: 'wizard',
        path: 'wizard',
        component: 'wizard',
        getTitle: () => i18n.t('pages.wizard.title'),
        auth: false,
        data: { streams: [] },
        sidebar: { include: false, parent: null },
        layout: { hideSidebar: true, exclusive: true }
    },
    {
        id: 'modelDetail',
        reconstruction: READ_ROUTE_RECONSTRUCTION,
        path: 'model/:id',
        component: 'modelDetail',
        getTitle: () => i18n.t('pages.modelDetail.title'),
        auth: true,
        data: { streams: [MODELS, PLUGINS] },
        sidebar: { include: false, parent: 'models' }
    }
];

export { ROUTE_DEFINITIONS_RAW };
