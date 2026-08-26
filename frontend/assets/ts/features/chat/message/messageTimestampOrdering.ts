/* SoAI - Canonical timestamp ordering for in-memory conversation messages [frontend/assets/ts/features/chat/message/messageTimestampOrdering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type TimestampedMessage = { timestamp?: number };

const resolveMessageTimestampInsertIndex = <Message extends TimestampedMessage>(messages: readonly Message[], timestamp: number): number => {
    if (!Number.isFinite(timestamp)) {
        return messages.length;
    }
    let insertIndex = messages.length;
    while (insertIndex > 0) {
        const prior = messages[insertIndex - 1];
        const priorTimestamp = typeof prior?.timestamp === 'number' && Number.isFinite(prior.timestamp) ? prior.timestamp : null;
        if (priorTimestamp !== null && priorTimestamp > timestamp) {
            insertIndex -= 1;
            continue;
        }
        break;
    }
    return insertIndex;
};

const insertMessageByTimestamp = <Message extends TimestampedMessage>(messages: Message[], message: Message, timestamp: number): void => {
    messages.splice(resolveMessageTimestampInsertIndex(messages, timestamp), 0, message);
};

export { insertMessageByTimestamp, resolveMessageTimestampInsertIndex };
