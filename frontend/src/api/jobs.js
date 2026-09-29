import client from './client';

// Poll only the job belonging to the currently attached file. The caller
// aborts the signal on replacement or unmount; no stale result reaches a form.
export async function waitForJob(jobId, signal, onState) {
  while (true) {
    if (signal?.aborted) throw new DOMException('Canceled', 'AbortError');
    const { data } = await client.get(`/jobs/${jobId}/`, { signal });
    onState?.(data.state);
    if (data.state === 'succeeded') return data.result;
    if (data.state === 'failed') {
      const err = new Error(data.error?.error?.message || 'Processing failed.');
      err.response = { status: data.error?.status || 500, data: data.error };
      throw err;
    }
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        signal?.removeEventListener('abort', abort);
        resolve();
      }, 1600);
      const abort = () => {
        clearTimeout(timer);
        reject(new DOMException('Canceled', 'AbortError'));
      };
      signal?.addEventListener('abort', abort, { once: true });
    });
  }
}
