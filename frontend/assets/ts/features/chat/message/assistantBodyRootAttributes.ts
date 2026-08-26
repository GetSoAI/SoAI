/* SoAI - Canonical assistant body root attribute rendering [frontend/assets/ts/features/chat/message/assistantBodyRootAttributes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, formatAssistantBodySegmentSignature } from '@features/chat/message/assistantMessageMarkupParts.ts';

type AssistantBodyAttributeHost = {
    escapeAttribute(value: string): string;
};

const injectAssistantBodyRootAttributes = (host: AssistantBodyAttributeHost, markup: string, key: string, signature: string): string => {
    const trimmed = markup.trim();
    const closeIndex = trimmed.indexOf('>');
    if (closeIndex <= 0 || !trimmed.startsWith('<') || trimmed.startsWith('</')) {
        throw new Error('Assistant body item markup must contain one root element.');
    }
    const keyAttribute = `${ASSISTANT_BODY_KEY_ATTRIBUTE_NAME}="${host.escapeAttribute(key)}"`;
    const signatureAttribute = `${ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME}="${host.escapeAttribute(formatAssistantBodySegmentSignature(signature))}"`;
    return `${trimmed.slice(0, closeIndex)} ${keyAttribute} ${signatureAttribute}${trimmed.slice(closeIndex)}`;
};

export { injectAssistantBodyRootAttributes };
