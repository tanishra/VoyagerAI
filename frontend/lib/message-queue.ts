import {
  putQueuedMessage,
  getQueuedMessages,
  deleteQueuedMessage,
  type QueuedMessage,
} from './offline-db';

function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

export async function queueMessage(
  threadId: string | null,
  content: string,
): Promise<QueuedMessage> {
  const msg: QueuedMessage = {
    id: generateId(),
    thread_id: threadId,
    content,
    created_at: Date.now(),
  };
  await putQueuedMessage(msg);
  return msg;
}

export async function replayQueuedMessages(
  sendFn: (msg: QueuedMessage) => Promise<boolean>,
): Promise<number> {
  const messages = await getQueuedMessages();
  let sentCount = 0;

  for (const msg of messages) {
    try {
      const success = await sendFn(msg);
      if (success) {
        await deleteQueuedMessage(msg.id);
        sentCount++;
      } else {
        break;
      }
    } catch {
      break;
    }
  }

  return sentCount;
}

export async function getQueuedCount(): Promise<number> {
  const messages = await getQueuedMessages();
  return messages.length;
}

export type { QueuedMessage };
