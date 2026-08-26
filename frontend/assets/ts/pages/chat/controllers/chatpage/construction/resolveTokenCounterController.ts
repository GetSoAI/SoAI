/* SoAI - Chat page resolve token counter controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/resolveTokenCounterController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/public.ts';
import type { ChatTokenCounterController } from '@pages/chat/widgets/tokencounter/ChatTokenCounterController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type TokenCounterControllerHost = PageDomOwnerHost & {
    getTokenCounterController: () => ChatTokenCounterController | null;
    setTokenCounterController: (controller: ChatTokenCounterController | null) => void;
};

const resolveTokenCounterControllerForPage = (host: TokenCounterControllerHost): ChatTokenCounterController | null => {
    const tokenCounterController = host.getTokenCounterController();
    if (!tokenCounterController) {
        return null;
    }
    if (host.pageDom.query(CHAT_SELECTORS.TOKEN_COUNTER_BTN).length === 0) {
        tokenCounterController.dispose();
        host.setTokenCounterController(null);
        return null;
    }
    return tokenCounterController;
};

export { resolveTokenCounterControllerForPage };
