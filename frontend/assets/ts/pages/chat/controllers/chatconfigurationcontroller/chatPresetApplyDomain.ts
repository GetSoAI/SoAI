/* SoAI - Chat preset staging application operation [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatPresetApplyDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { CHAT_PRESET_SECTION_DEFINITIONS, translateChatPresetSection, type ChatPresetSectionId } from '@features/chat/public.ts';
import { reportChatPresetActionFailure } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetLibraryMutationDomain.ts';
import type { ChatPresetConfigurationPort } from '@pages/chat/controllers/chatconfigurationcontroller/contracts.ts';
import type { WebuiChatPresetRecord } from '@core/api/contracts/webuiChatPresetContractTypes.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

const sectionNames = (sectionIds: readonly ChatPresetSectionId[]): string =>
    CHAT_PRESET_SECTION_DEFINITIONS.filter((definition) => sectionIds.includes(definition.id))
        .map((definition) => translateChatPresetSection(definition.id))
        .join(', ');

const executeChatPresetApply = async (options: { record: WebuiChatPresetRecord; configuration: ChatPresetConfigurationPort; isSessionActive: () => boolean; show: (message: string, type: 'error' | 'info' | 'success' | 'warning') => void }): Promise<void> => {
    try {
        const dirty = options.configuration.dirtySections(options.record);
        const accepted = dirty.length === 0 || (await requireDialogsService().showConfirmation({ title: i18n.t('chat.configuration.presetLibrary.applyConfirmTitle'), message: i18n.t('chat.configuration.presetLibrary.applyConfirmMessage', { sections: sectionNames(dirty) }), confirmText: i18n.t('chat.configuration.presetLibrary.applyAction'), cancelText: i18n.t('common.cancel') }));
        if (!accepted || !options.isSessionActive()) return;
        const result = await options.configuration.apply(options.record, options.isSessionActive);
        if (!result || !options.isSessionActive()) return;
        const appliedSections = sectionNames(result.appliedSections);
        const message = result.skippedValues.length > 0 ? (result.appliedSections.length > 0 ? i18n.t('chat.configuration.presetLibrary.appliedWithSkipped', { sections: appliedSections, count: result.skippedValues.length }) : i18n.t('chat.configuration.presetLibrary.skippedOnly', { count: result.skippedValues.length })) : !result.changed ? i18n.t('chat.configuration.presetLibrary.noChanges') : i18n.t('chat.configuration.presetLibrary.appliedSummary', { sections: appliedSections });
        options.show(message, result.skippedValues.length > 0 ? 'warning' : result.changed ? 'success' : 'info');
    } catch (error) {
        if (!options.isSessionActive()) {
            errorHandler.error('ChatPresetLibrary', 'Preset apply failed', ensureError(error));
            return;
        }
        reportChatPresetActionFailure(error, 'Preset apply failed', 'chat.configuration.presetLibrary.applyFailed', (message) => options.show(message, 'error'));
    }
};

export { executeChatPresetApply };
