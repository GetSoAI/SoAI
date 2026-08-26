/* SoAI - Frontend help section definitions [frontend/assets/ts/features/help/sections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { StructuredTextSection } from '@core/richtextrenderer/structuredSections.ts';

const HELP_SECTIONS = Object.freeze([
    {
        id: 'getting-started',
        getTitle: () => i18n.t('help.sections.gettingStarted.sectionTitle'),
        getHeading: () => i18n.t('help.sections.gettingStarted.heading'),
        blocks: [
            { type: 'paragraph', getText: () => i18n.t('help.sections.gettingStarted.intro') },
            {
                type: 'list',
                ordered: true,
                items: [{ getText: () => i18n.t('help.sections.gettingStarted.localBackend') }, { getText: () => i18n.t('help.sections.gettingStarted.localModel') }, { getText: () => i18n.t('help.sections.gettingStarted.remoteModel') }, { getText: () => i18n.t('help.sections.gettingStarted.chat') }, { getText: () => i18n.t('help.sections.gettingStarted.api') }, { getText: () => i18n.t('help.sections.gettingStarted.troubleshooting') }]
            }
        ]
    },
    {
        id: 'chat-tools',
        getTitle: () => i18n.t('help.sections.chatTools.sectionTitle'),
        getHeading: () => i18n.t('help.sections.chatTools.heading'),
        blocks: [
            { type: 'paragraph', getText: () => i18n.t('help.sections.chatTools.conversations') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.chatTools.tools') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.chatTools.mcp') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.chatTools.voice') }
        ]
    },
    {
        id: 'models',
        getTitle: () => i18n.t('help.sections.models.sectionTitle'),
        getHeading: () => i18n.t('help.sections.models.heading'),
        blocks: [
            { type: 'paragraph', getText: () => i18n.t('help.sections.models.catalog') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.models.virtualModels') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.models.plugins') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.models.bundled') },
            {
                type: 'list',
                items: [{ getText: () => i18n.t('help.sections.models.engineGguf') }, { getText: () => i18n.t('help.sections.models.engineVllm') }, { getText: () => i18n.t('help.sections.models.engineCtranslate2') }, { getText: () => i18n.t('help.sections.models.engineWhisper') }, { getText: () => i18n.t('help.sections.models.engineMeloTts') }, { getText: () => i18n.t('help.sections.models.engineEmbeddings') }, { getText: () => i18n.t('help.sections.models.engineExternal') }]
            }
        ]
    },
    {
        id: 'files-knowledge',
        getTitle: () => i18n.t('help.sections.filesKnowledge.sectionTitle'),
        getHeading: () => i18n.t('help.sections.filesKnowledge.heading'),
        blocks: [
            { type: 'paragraph', getText: () => i18n.t('help.sections.filesKnowledge.files') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.filesKnowledge.knowledge') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.filesKnowledge.prompts') }
        ]
    },
    {
        id: 'administration',
        getTitle: () => i18n.t('help.sections.administration.sectionTitle'),
        getHeading: () => i18n.t('help.sections.administration.heading'),
        blocks: [
            { type: 'paragraph', getText: () => i18n.t('help.sections.administration.status') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.administration.operations') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.administration.maintenance') }
        ]
    },
    {
        id: 'access',
        getTitle: () => i18n.t('help.sections.access.sectionTitle'),
        getHeading: () => i18n.t('help.sections.access.heading'),
        blocks: [
            { type: 'paragraph', getText: () => i18n.t('help.sections.access.access') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.access.users') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.access.network') },
            { type: 'paragraph', getText: () => i18n.t('help.sections.access.plugins') }
        ]
    }
]) satisfies ReadonlyArray<StructuredTextSection>;

export { HELP_SECTIONS };
