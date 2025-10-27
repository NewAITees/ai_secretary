export interface VoicePlan {
  text: string;
  speakerUuid: string;
  styleId: number;
  speedScale: number;
  volumeScale: number;
  pitchScale: number;
  intonationScale: number;
  prePhonemeLength: number;
  postPhonemeLength: number;
  outputSamplingRate: number;
  prosodyDetail: unknown[];
}

export interface ChatResponsePayload {
  voice_plan?: VoicePlan | null;
  audio_path?: string | null;
  played_audio: boolean;
  raw_response?: Record<string, unknown> | null;
}

export async function postChatMessage(
  message: string,
  playAudio: boolean,
  model?: string,
): Promise<ChatResponsePayload> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, play_audio: playAudio, model }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `API request failed with status ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  const payload = (await response.json()) as ChatResponsePayload;
  return payload;
}

export async function getAvailableModels(): Promise<string[]> {
  const response = await fetch('/api/models', {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new Error(
      `API request failed with status ${response.status}${detail ? `: ${detail}` : ''}`,
    );
  }

  const payload = (await response.json()) as { models: string[] };
  return payload.models;
}
