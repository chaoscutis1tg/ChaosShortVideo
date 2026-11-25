// Typed API & WebSocket client communicating strictly with Module M07

async function requestJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const studioApi = {
  getSystemStatus: () => requestJSON('/api/system/status'),
  selectGpuDevice: (device_id) =>
    requestJSON('/api/system/gpu-select', {
      method: 'POST',
      body: JSON.stringify({ device_id }),
    }),
  cleanupTempStorage: () => requestJSON('/api/system/cleanup-temp', { method: 'POST' }),
  updateApiKeys: (payload) =>
    requestJSON('/api/system/settings', { method: 'POST', body: JSON.stringify(payload) }),
  getLanQrImageUrl: (url) => `/api/system/lan-qr?url=${encodeURIComponent(url || '')}`,
  getStoreBackupExportUrl: () => '/api/system/backup-export',
  async importStoreBackupZip(file) {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/system/backup-import', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Khôi phục dữ liệu sao lưu thất bại');
    }
    return res.json();
  },

  listBgmPresets: () => requestJSON('/api/bgm'),
  listVoices: () => requestJSON('/api/voices'),
  previewVoice: (profile_id, sample_text, speed_rate = null, pitch_hz = null) =>
    requestJSON('/api/voices/preview', {
      method: 'POST',
      body: JSON.stringify({ profile_id, sample_text, speed_rate, pitch_hz }),
    }),

  async uploadCloneVoice(formData) {
    const res = await fetch('/api/voices/clone-sample', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Tải mẫu giọng thất bại');
    }
    return res.json();
  },

  async uploadStudioFile(file, category = 'video') {
    const fd = new FormData();
    fd.append('category', category);
    fd.append('file', file);
    const res = await fetch('/api/uploads/file', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Tải tệp lên thất bại');
    }
    return res.json();
  },

  async uploadBatchFiles(files, category = 'product_photo') {
    const fd = new FormData();
    fd.append('category', category);
    Array.from(files).forEach((file) => fd.append('files', file));
    const res = await fetch('/api/uploads/batch', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Tải danh sách ảnh sản phẩm thất bại');
    }
    return res.json();
  },

  probeVideoUrl: (url) =>
    requestJSON('/api/media/probe-url', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),

  trimMediaSegment: (local_path, start_ms, end_ms) =>
    requestJSON('/api/media/trim', {
      method: 'POST',
      body: JSON.stringify({ local_path, start_ms, end_ms }),
    }),

  renderTrueFrameSnapshot: (payload) =>
    requestJSON('/api/preview/render-frame', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  startTopicProject: (payload) =>
    requestJSON('/api/topic/start', { method: 'POST', body: JSON.stringify(payload) }),

  startMovieProject: (payload) =>
    requestJSON('/api/movie/start', { method: 'POST', body: JSON.stringify(payload) }),

  startProductProject: (payload) =>
    requestJSON('/api/product/start', { method: 'POST', body: JSON.stringify(payload) }),

  checkProductCompliance: (text) =>
    requestJSON('/api/product/compliance-check', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  scrapeProductUrl: (url) =>
    requestJSON('/api/product/scrape-url', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),

  startProductBatchUrls: (payload) =>
    requestJSON('/api/product/batch-urls', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  previewPhotoCutout: (local_path) =>
    requestJSON('/api/product/preview-cutout', {
      method: 'POST',
      body: JSON.stringify({ local_path }),
    }),

  getBrandKit: () => requestJSON('/api/brand-kit'),

  saveBrandKit: (payload) =>
    requestJSON('/api/brand-kit', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getProjectZipUrl: (projectId) => `/api/projects/${projectId}/download-zip`,

  listProductTemplates: () => requestJSON('/api/product/templates'),

  saveProductTemplate: (payload) =>
    requestJSON('/api/product/templates', { method: 'POST', body: JSON.stringify(payload) }),

  deleteProductTemplate: (templateId) =>
    requestJSON(`/api/product/templates/${templateId}`, { method: 'DELETE' }),

  listProjects: () => requestJSON('/api/projects'),
  getProjectDetail: (projectId) => requestJSON(`/api/projects/${projectId}`),

  renderApprovedProject: (projectId, payload) =>
    requestJSON(`/api/projects/${projectId}/render`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  pauseProject: (projectId) =>
    requestJSON(`/api/projects/${projectId}/pause`, { method: 'POST' }),

  resumeProject: (projectId) =>
    requestJSON(`/api/projects/${projectId}/resume`, { method: 'POST' }),

  cancelProject: (projectId) =>
    requestJSON(`/api/projects/${projectId}/cancel`, { method: 'POST' }),

  deleteProject: (projectId) =>
    requestJSON(`/api/projects/${projectId}`, { method: 'DELETE' }),

  translateProjectToVi: (projectId) =>
    requestJSON(`/api/projects/${projectId}/translate-vi`, { method: 'POST' }),

  openOutputFolder: (projectId) =>
    requestJSON(`/api/projects/${projectId}/open-folder`, { method: 'POST' }),

  retryProject: (projectId) =>
    requestJSON(`/api/projects/${projectId}/retry`, { method: 'POST' }),

  connectProgressSocket(projectId, onEvent) {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/progress/${projectId}`);
    ws.onmessage = (ev) => {
      try {
        onEvent(JSON.parse(ev.data));
      } catch {
        // ignore malformed frame
      }
    };
    return ws;
  },
};
