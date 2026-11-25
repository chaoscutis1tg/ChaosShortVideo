import React, { useState } from 'react';
import { KeyRound, Save, X } from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';

export default function SettingsModal({ systemStatus, onClose, onUpdated, notify }) {
  const [geminiKey, setGeminiKey] = useState('');
  const [pexelsKey, setPexelsKey] = useState('');
  const [pixabayKey, setPixabayKey] = useState('');
  const [elevenKey, setElevenKey] = useState('');
  const [fptKey, setFptKey] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {};
      if (geminiKey.trim()) payload.gemini_api_key = geminiKey.trim();
      if (pexelsKey.trim()) payload.pexels_api_key = pexelsKey.trim();
      if (pixabayKey.trim()) payload.pixabay_api_key = pixabayKey.trim();
      if (elevenKey.trim()) payload.elevenlabs_api_key = elevenKey.trim();
      if (fptKey.trim()) payload.fpt_ai_api_key = fptKey.trim();

      const updated = await studioApi.updateApiKeys(payload);
      onUpdated(updated);
      notify('Đã lưu cấu hình khóa kết nối vào máy.');
      onClose();
    } catch (err) {
      notify(`Lỗi lưu cấu hình: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const keys = systemStatus?.keys_configured || {};

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.72)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 110,
        padding: 16,
      }}
    >
      <form
        className="card"
        onSubmit={handleSave}
        style={{ width: '100%', maxWidth: 580, marginBottom: 0 }}
      >
        <div className="page-header" style={{ marginBottom: 14 }}>
          <div>
            <div className="page-title">
              <KeyRound size={18} /> Cấu hình khóa kết nối dịch vụ
            </div>
            <div className="page-subtitle">
              Lưu cục bộ trong tệp .env trên máy tính của bạn
            </div>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            <X size={15} /> Đóng
          </button>
        </div>

        <div className="form-group">
          <label className="form-label">
            Google Gemini API Key{' '}
            <span style={{ color: keys.gemini ? '#34d399' : '#fbbf24' }}>
              ({keys.gemini ? 'Đã kết nối' : 'Chưa nhập'})
            </span>
          </label>
          <input
            type="password"
            className="input"
            placeholder="Nhập khóa mới nếu muốn thay đổi..."
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
          />
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">
              Pexels API Key ({keys.pexels ? 'Đã có' : 'Tùy chọn'})
            </label>
            <input
              type="password"
              className="input"
              placeholder="PEXELS_API_KEY"
              value={pexelsKey}
              onChange={(e) => setPexelsKey(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">
              Pixabay API Key ({keys.pixabay ? 'Đã có' : 'Tùy chọn'})
            </label>
            <input
              type="password"
              className="input"
              placeholder="PIXABAY_API_KEY"
              value={pixabayKey}
              onChange={(e) => setPixabayKey(e.target.value)}
            />
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">
              ElevenLabs API Key ({keys.elevenlabs ? 'Đã có' : 'Tùy chọn'})
            </label>
            <input
              type="password"
              className="input"
              placeholder="ELEVENLABS_API_KEY"
              value={elevenKey}
              onChange={(e) => setElevenKey(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">
              FPT.AI TTS Key ({keys.fpt_ai ? 'Đã có' : 'Tùy chọn'})
            </label>
            <input
              type="password"
              className="input"
              placeholder="FPT_AI_API_KEY"
              value={fptKey}
              onChange={(e) => setFptKey(e.target.value)}
            />
          </div>
        </div>

        <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={15} /> Lưu cấu hình
          </button>
        </div>
      </form>
    </div>
  );
}
