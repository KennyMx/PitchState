import type { Analysis, Frame } from './model';
export async function analyzeVideo(
  file: File,
  onProgress: (n: number) => void,
  signal: AbortSignal,
): Promise<Analysis> {
  if (file.size > 100 * 1024 * 1024) throw new Error('Choose a clip smaller than 100 MB.');
  const url = URL.createObjectURL(file),
    video = document.createElement('video');
  video.muted = true;
  video.preload = 'auto';
  video.src = url;
  const worker = new Worker(new URL('../workers/tracking.worker.ts', import.meta.url), {
    type: 'module',
  });
  const waitEvent = (name: string) =>
    new Promise<void>((resolve, reject) => {
      const cleanup = () => {
        clearTimeout(timer);
        video.removeEventListener(name, ok);
        video.removeEventListener('error', fail);
        signal.removeEventListener('abort', abort);
      };
      const ok = () => {
          cleanup();
          resolve();
        },
        fail = () => {
          cleanup();
          reject(new Error('This video could not be decoded. Try an MP4 (H.264) or WebM clip.'));
        },
        abort = () => {
          cleanup();
          reject(new DOMException('Cancelled', 'AbortError'));
        };
      const timer = setTimeout(fail, 15000);
      video.addEventListener(name, ok, { once: true });
      video.addEventListener('error', fail, { once: true });
      signal.addEventListener('abort', abort, { once: true });
      if (signal.aborted) abort();
    });
  try {
    await waitEvent('loadeddata');
    if (!Number.isFinite(video.duration) || video.duration < 1 || video.duration > 60)
      throw new Error('Choose a clip between 1 and 60 seconds.');
    const canvas = document.createElement('canvas');
    const scale = Math.min(1, 480 / Math.max(video.videoWidth, video.videoHeight));
    canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
    canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
    const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
    const frames: Frame[] = [];
    for (let time = 0; time < video.duration; time += 0.2) {
      if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
      if (time > 0) {
        const seek = waitEvent('seeked');
        video.currentTime = time;
        await seek;
      }
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const frame = await new Promise<Frame>((resolve, reject) => {
        const timer = setTimeout(() => {
          cleanup();
          reject(new Error('Tracking timed out. Try a shorter clip.'));
        }, 10000);
        const cleanup = () => {
          clearTimeout(timer);
          signal.removeEventListener('abort', abort);
        };
        const abort = () => {
          cleanup();
          reject(new DOMException('Cancelled', 'AbortError'));
        };
        signal.addEventListener('abort', abort, { once: true });
        worker.onmessage = (e) => {
          cleanup();
          resolve(e.data);
        };
        worker.onerror = () => {
          cleanup();
          reject(new Error('Local tracking failed.'));
        };
        worker.postMessage(
          { data: pixels.data, width: canvas.width, height: canvas.height, time },
          [pixels.data.buffer],
        );
      });
      frames.push(frame);
      onProgress(Math.min(100, Math.round(((time + 0.2) / video.duration) * 100)));
    }
    return {
      frames,
      duration: video.duration,
      events: [],
      source: 'local',
      name: file.name.replace(/\.[^.]+$/, ''),
    };
  } finally {
    worker.terminate();
    video.removeAttribute('src');
    video.load();
    URL.revokeObjectURL(url);
  }
}
