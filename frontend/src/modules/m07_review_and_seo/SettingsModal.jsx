import React, { useState } from 'react';
import { Archive, CheckCircle2, Download, KeyRound, Save, Upload, X } from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';

export default function SettingsModal({
  systemStatus,
  onClose,
  onUpdated,
  onBackupRestored,
  notify,
}) {
  const [geminiKey, setGeminiKey] = useState('');
  const [pexelsKey, setPexelsKey] = useState('');
  const [pixabayKey, setPixabayKey] = useState('');
  const [elevenKey, setElevenKey] = useState('');
  const [fptKey, setFptKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [restoringBackup, setRestoringBackup] = useState(false);

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

  const handleImportBackup = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRestoringBackup(true);
    try {
      const res = await studioApi.importStoreBackupZip(file);
      if (onBackupRestored) await onBackupRestored();
      notify(
        `Đã khôi phục ${res.templates_restored || 0} mẫu sản phẩm, Bộ nhận diện thương hiệu & ${
          res.voices_restored || 0
        } giọng nhân bản.`
      );
    } catch (err) {
      notify(`Lỗi khôi phục gói sao lưu: ${err.message}`);
    } finally {
      setRestoringBackup(false);
      e.target.value = '';
    }
  };

  const keys = systemStatus?.keys_configured || {};

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(2, 6, 23, 0.74)',
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
        style={{
          width: '100%',
          maxWidth: 640,
          maxHeight: '92vh',
          overflowY: 'auto',
          marginBottom: 0,
        }}
      >
        <div className="page-header" style={{ marginBottom: 14 }}>
          <div>
            <div className="page-title">
              <KeyRound size={19} /> Cài đặt Kết nối API & Sao lưu Cửa hàng
            </div>
            <div className="page-subtitle">
              Quản lý khóa bảo mật cục bộ (.env) và đóng gói dữ liệu cửa hàng mang sang máy khác
            </div>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            <X size={15} /> Đóng
          </button>
        </div>

        {/* SECTION 1: API KEYS */}
        <div className="step-box" style={{ padding: 14, marginBottom: 14 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 6,
            }}
          >
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

        {/* SECTION 2: STORE BACKUP & RESTORE (.ZIP) — ITEM 8 */}
        <div className="step-box" style={{ padding: 14, marginBottom: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Archive size={16} style={{ color: 'var(--brand-text)' }} />
            <strong style={{ fontSize: 13.8 }}>
              Sao lưu & Khôi phục dữ liệu cửa hàng (Backup / Restore)
            </strong>
          </div>
          <div className="text-sub" style={{ fontSize: 12.4, marginBottom: 10, lineHeight: 1.45 }}>
            Đóng gói trọn bộ <strong>Kho mẫu sản phẩm</strong>, <strong>Bộ nhận diện thương hiệu (Brand Kit + Logo)</strong> và <strong>Giọng thu mẫu riêng</strong> ra 1 tệp <code>.ZIP</code> duy nhất để cất giữ an toàn hoặc chuyển sang máy tính khác.
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <a
              href={studioApi.getStoreBackupExportUrl()}
              download="ChaosShortVideo_StoreBackup.zip"
              className="btn btn-secondary btn-sm"
              style={{ textDecoration: 'none' }}
            >
              <Download size={14} /> Xuất gói Sao lưu (.ZIP)
            </a>
            <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
              <Upload size={14} />{' '}
              {restoringBackup ? 'Đang khôi phục...' : 'Khôi phục từ tệp Sao lưu (.ZIP)'}
              <input
                type="file"
                accept=".zip,application/zip"
                hidden
                disabled={restoringBackup}
                onChange={handleImportBackup}
              />
            </label>
          </div>
        </div>

        <div className="btn-row" style={{ justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Đóng
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={15} /> {saving ? 'Đang lưu...' : 'Lưu khóa API'}
          </button>
        </div>
      </form>
    </div>
  );
}
