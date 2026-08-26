/* SoAI - Chat configuration Save UI binding [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/chatConfigurationSaveBindingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import type { SaveController } from '@core/save/public.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/public.ts';
import type { ConfigurationControllerHost } from '@pages/chat/controllers/chatconfigurationcontroller/types.ts';

const attachChatConfigurationSave = (save: SaveController, host: ConfigurationControllerHost): void => {
    const modalRoot = requireModalPresenter().requireElement(CHAT_CONFIGURATION_MODAL_ID);
    setAriaBusy(modalRoot, false);
    save.attach({
        resolveSaveButtons: () => {
            const button = host.pageDom.optional('.chat-configuration-save-btn', modalRoot);
            return button instanceof HTMLButtonElement ? [button] : [];
        },
        busyRoots: [modalRoot],
        autoNotifyRoot: modalRoot
    });
};

export { attachChatConfigurationSave };
