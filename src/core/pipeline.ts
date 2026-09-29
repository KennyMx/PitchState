import type { Analysis, Frame } from './model';
export interface Choice {
  choice: string;
  confidence: number;
  probabilities: Record<string, number>;
}
export interface Judgment {
  time: number;
  source: 'jev' | 'unavailable';
  model?: string;
  cached?: boolean;
  nextAction?: Choice;
  phase?: Choice;
  dangerousRunProbability?: number;
  latencyMs?: number;
  reason?: string;
  usage?: { input_tokens: number; output_tokens: number };
}
export interface Health {
  ready: boolean;
  jevConfigured: boolean;
  demoAvailable: boolean;
  budget: { completedCalls: number; estimatedCostUsd: number };
}
export interface PipelineState {
  possession: string;
  carrierId: number | null;
  phase: string;
  homeAttacksRight: boolean;
  possessionConfidence: number;
  teams: Record<
    string,
    {
      visiblePlayers: number;
      widthMeters: number | null;
      depthMeters: number | null;
      centroid: number[] | null;
    }
  >;
  evidence: {
    pressureCount: number;
    closingOpponents: number[];
    openPassOptions: number[];
    ballSpeedMps: number | null;
    forwardProgressMps: number | null;
    finalThird: boolean;
    localAttackers: number;
    localDefenders: number;
    overload: boolean;
    dangerousRunIds: number[];
    secondsSinceTurnover: number | null;
  };
}
export const humanize = (s: string) => s.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase());
export function judgmentAt(analysis: Analysis, time: number): Judgment | undefined {
  return analysis.judgments?.filter((j) => j.time <= time).at(-1);
}
export function rawFrameAt(frames: Frame[], time: number) {
  return frames.filter((f) => f.time <= time).at(-1) ?? frames[0];
}
async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Inference service returned ${response.status}`);
  }
  return response.json();
}
export async function getHealth(): Promise<Health> {
  return request('/api/health');
}
export async function loadRealDemo(): Promise<Analysis> {
  return request('/api/demo/analysis');
}
export async function analyzeWithPipeline(
  file: File,
  onProgress: (n: number, stage: string) => void,
  signal: AbortSignal,
  homeAttacksRight = true,
): Promise<Analysis> {
  if (file.size > 100 * 1024 * 1024) throw new Error('Choose a clip smaller than 100 MB.');
  await getHealth();
  const form = new FormData();
  form.append('video', file);
  form.append('use_jev', 'true');
  form.append('home_attacks_right', String(homeAttacksRight));
  const job = await request<{ id: string }>('/api/jobs', { method: 'POST', body: form, signal });
  const cancel = () => {
    void fetch(`/api/jobs/${job.id}`, { method: 'DELETE' });
  };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    while (!signal.aborted) {
      const status = await request<{
        status: string;
        progress: number;
        stage: string;
        error?: string;
      }>(`/api/jobs/${job.id}`, { signal });
      onProgress(status.progress, status.stage);
      if (status.status === 'complete') {
        const result = await request<Analysis>(`/api/jobs/${job.id}/analysis`, { signal });
        return { ...result, videoUrl: `/api/jobs/${job.id}/video` };
      }
      if (status.status === 'failed' || status.status === 'cancelled')
        throw new Error(status.error ?? 'Analysis cancelled');
      await new Promise<void>((resolve, reject) => {
        const stop = () => {
          clearTimeout(timer);
          reject(new DOMException('Cancelled', 'AbortError'));
        };
        const timer = setTimeout(() => {
          signal.removeEventListener('abort', stop);
          resolve();
        }, 900);
        signal.addEventListener('abort', stop, { once: true });
      });
    }
    cancel();
    throw new DOMException('Cancelled', 'AbortError');
  } finally {
    signal.removeEventListener('abort', cancel);
  }
}
