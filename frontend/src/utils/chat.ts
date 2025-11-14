import type {
  ChatHistoryMessage,
  ChatResponsePayload,
  VoicePlan,
} from '../api';
import type { MessageEntry } from '../types/chat';

export function formatTimestamp(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString();
}

export function formatSessionTimestamp(value: string | null | undefined): string {
  if (!value) {
    return '未記録';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function createId(): string {
  return crypto.randomUUID();
}

export function buildVoicePlanFromRaw(raw: unknown): VoicePlan | null {
  if (typeof raw !== 'object' || raw === null) {
    return null;
  }
  const data = raw as Record<string, unknown>;
  const requiredKeys = [
    'text',
    'speakerUuid',
    'styleId',
    'speedScale',
    'volumeScale',
    'pitchScale',
    'intonationScale',
    'prePhonemeLength',
    'postPhonemeLength',
    'outputSamplingRate',
  ];
  if (!requiredKeys.every(key => key in data)) {
    return null;
  }
  try {
    return {
      text: String(data.text ?? ''),
      speakerUuid: String(data.speakerUuid ?? ''),
      styleId: Number(data.styleId ?? 0),
      speedScale: Number(data.speedScale ?? 1),
      volumeScale: Number(data.volumeScale ?? 1),
      pitchScale: Number(data.pitchScale ?? 0),
      intonationScale: Number(data.intonationScale ?? 1),
      prePhonemeLength: Number(data.prePhonemeLength ?? 0),
      postPhonemeLength: Number(data.postPhonemeLength ?? 0),
      outputSamplingRate: Number(data.outputSamplingRate ?? 24000),
      prosodyDetail: Array.isArray(data.prosodyDetail) ? data.prosodyDetail : [],
    };
  } catch {
    return null;
  }
}

export function parseAssistantContent(
  rawContent: string,
): { text: string; payload?: ChatResponsePayload } {
  try {
    const parsed = JSON.parse(rawContent);
    if (typeof parsed !== 'object' || parsed === null) {
      return {
        text: typeof parsed === 'string' ? parsed : rawContent,
      };
    }
    const data = parsed as Record<string, unknown>;
    const voicePlan = buildVoicePlanFromRaw(data);
    const audioValue = data['audio_path'];
    const playedValue = data['played_audio'];
    const textValue = data['text'];
    const payload: ChatResponsePayload = {
      voice_plan: voicePlan,
      audio_path: typeof audioValue === 'string' ? audioValue : null,
      played_audio:
        typeof playedValue === 'boolean' ? playedValue : Boolean(playedValue),
      raw_response: data,
    };
    const text =
      voicePlan?.text || (typeof textValue === 'string' ? textValue : rawContent);
    return { text, payload };
  } catch {
    return { text: rawContent };
  }
}

export function convertHistoryMessages(messages: ChatHistoryMessage[]): MessageEntry[] {
  const baseTime = Date.now();
  let index = 0;
  return messages
    .filter(message => message.role === 'user' || message.role === 'assistant')
    .map(message => {
      index += 1;
      if (message.role === 'assistant') {
        const parsed = parseAssistantContent(message.content);
        return {
          id: createId(),
          role: 'assistant',
          content: parsed.text,
          details: parsed.payload,
          timestamp: baseTime + index,
        } satisfies MessageEntry;
      }
      return {
        id: createId(),
        role: 'user',
        content: message.content,
        timestamp: baseTime + index,
      } satisfies MessageEntry;
    });
}
