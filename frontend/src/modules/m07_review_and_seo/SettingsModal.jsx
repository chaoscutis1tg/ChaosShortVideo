import React, { useState } from 'react';
import { CheckCircle2, KeyRound, Save, X } from 'lucide-react';
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
      notify('Đã lưu cấu hình khóa kết nối cho ChaosShortVideo.');
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
        background: 'rgba(2, 6, 23, 0.72)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 110,
        padding: 16,
      }}
      onClick={onClose}
    >
      <form
        className="card"
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSave}
        style={{ width: '100%', maxWidth: 600, marginBottom: 0 }}
      >
        <div className="page-header" style={{ marginBottom: 14 }}>
          <div>
            <div className="page-title">
              <KeyRound size={19} /> Kết nối khóa API — ChaosShortVideo
            </div>
            <div className="page-subtitle">
              Khóa được bảo mật cục bộ trong tệp .env ngay trên máy của bạn
            </div>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            <X size={15} /> Đóng
          </button>
        </div>

        <div className="step-box" style={{ padding: 14, marginBottom: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Google Gemini API Key (Viết kịch bản, Nhìn ảnh sản phẩm & Dịch phim)
            </label>
            <span className={`badge ${keys.gemini ? 'badge-ok' : 'badge-warn'}`}>
              {keys.gemini ? (
                <>
                  <CheckCircle2 size={12} /> Đã kết nối
                </>
              ) : (
                'Chưa nhập'
              )}
            </span>
          </div>
          <input
            type="password"
            className="input"
            placeholder="Dán khóa mới nếu muốn cập nhật (để trống để giữ khóa hiện tại)..."
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
          />
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">
              Pexels API Key ({keys.pexels ? 'Đã có' : 'Tùy chọn cho Video Chủ Đề'})
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
              Pixabay API Key ({keys.pixabay ? 'Đã có' : 'Tùy chọn cho Video Chủ Đề'})
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
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Hủy
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={15} /> {saving ? 'Đang lưu...' : 'Lưu cấu hình'}
          </button>
        </div>
      </form>
    </div>
  );
}
