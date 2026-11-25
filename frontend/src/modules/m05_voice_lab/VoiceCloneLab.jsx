import React, { useState } from 'react';
import { Mic, Play, Plus, RotateCcw, Upload, Volume2 } from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import { stripLeadingEmoji } from '../m00_core_contracts/constants';
import { MediaDropzone } from '../m00_core_contracts/StudioWidgets';

const SAMPLE_PRESETS = [
  {
    label: 'Nghệ nhân chia sẻ đàn Violin',
    text: 'Điểm chạm cảm xúc đầu tiên của cây đàn này nằm ở mặt top gỗ thịt tự nhiên nguyên tấm, cho âm vang dày và ấm ngay từ nốt kéo đầu tiên.',
  },
  {
    label: 'Tư vấn thời trang thanh lịch',
    text: 'Thiết kế phom dáng tinh tế giúp tôn nét thanh lịch tự nhiên, chất vải mềm thoáng mang lại sự thoải mái suốt cả ngày dài.',
  },
  {
    label: 'Thuyết minh phim kịch tính',
    text: 'Không ai ngờ rằng, người đàn ông trầm lặng bị cả gia tộc xem nhẹ này lại chính là chủ tịch tập đoàn.',
  },
];

export default function VoiceCloneLab({ voices, onVoicesChanged, notify }) {
  const [sampleText, setSampleText] = useState(SAMPLE_PRESETS[0].text);
  const [testSpeed, setTestSpeed] = useState(null);
  const [testPitch, setTestPitch] = useState(null);
  const [previewAudioUrl, setPreviewAudioUrl] = useState('');
  const [activeVoiceName, setActiveVoiceName] = useState('');
  const [loadingPreviewId, setLoadingPreviewId] = useState('');

  const [cloneName, setCloneName] = useState('');
  const [cloneRefText, setCloneRefText] = useState('');
  const [cloneSpeed, setCloneSpeed] = useState(1.04);
  const [cloneFile, setCloneFile] = useState(null);
  const [savingClone, setSavingClone] = useState(false);

  const handlePreview = async (voiceObj) => {
    setLoadingPreviewId(voiceObj.profile_id);
    try {
      const spd = testSpeed !== null ? testSpeed : voiceObj.speed_rate;
      const ptc = testPitch !== null ? testPitch : voiceObj.pitch_hz;
      const res = await studioApi.previewVoice(voiceObj.profile_id, sampleText, spd, ptc);
      setActiveVoiceName(
        `${stripLeadingEmoji(voiceObj.display_name)} (${spd.toFixed(2)}x, độ trầm ${ptc > 0 ? `+${ptc}` : ptc})`
      );
      setPreviewAudioUrl(`${res.audio_url}?t=${Date.now()}`);
    } catch (err) {
      notify(`Lỗi nghe thử giọng: ${err.message}`);
    } finally {
      setLoadingPreviewId('');
    }
  };

  const handleCreateClone = async (e) => {
    e.preventDefault();
    if (!cloneName.trim() || !cloneFile) {
      notify('Vui lòng đặt tên giọng và chọn tệp âm thanh mẫu (10–15 giây).');
      return;
    }
    setSavingClone(true);
    try {
      const fd = new FormData();
      fd.append('display_name', cloneName.trim());
      fd.append('sample_ref_text', cloneRefText);
      fd.append('speed_rate', String(cloneSpeed));
      fd.append('sample_file', cloneFile);
      await studioApi.uploadCloneVoice(fd);
      setCloneName('');
      setCloneRefText('');
      setCloneFile(null);
      await onVoicesChanged();
      notify('Đã tạo hồ sơ giọng đọc mới thành công.');
    } catch (err) {
      notify(`Không thể tạo giọng mẫu: ${err.message}`);
    } finally {
      setSavingClone(false);
    }
  };

  return (
    <div>
      <div className="card">
        <div className="page-header">
          <div>
            <div className="page-title">
              <Volume2 size={19} strokeWidth={1.9} /> Thư Viện {voices.length} Giọng Đọc Truyền Cảm & Tinh Chỉnh Độ Trầm Ấm
            </div>
            <div className="page-subtitle">
              Chọn câu mẫu, điều chỉnh tốc độ & độ trầm ấm bên dưới rồi bấm Nghe thử để chọn chất giọng ưng ý nhất
            </div>
          </div>
        </div>

        <div className="form-group">
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            {SAMPLE_PRESETS.map((sp, i) => (
              <button
                key={i}
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setSampleText(sp.text)}
              >
                {sp.label}
              </button>
            ))}
          </div>
          <textarea
            className="textarea"
            style={{ minHeight: 62 }}
            value={sampleText}
            onChange={(e) => setSampleText(e.target.value)}
          />
        </div>

        {/* Custom Speed & Pitch Audition Controls */}
        <div
          className="step-box"
          style={{ padding: '11px 14px', marginBottom: 14 }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <strong style={{ fontSize: 12.6 }}>
              Tinh chỉnh sắc thái khi nghe thử:{' '}
              <span style={{ color: '#9ca3af', fontWeight: 400 }}>
                {testSpeed === null && testPitch === null
                  ? 'Đang dùng thông số chuẩn của từng giọng'
                  : `Tốc độ ${(testSpeed ?? 1.04).toFixed(2)}x • Độ trầm ${(testPitch ?? 0).toFixed(1)}`}
              </span>
            </strong>
            {(testSpeed !== null || testPitch !== null) && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setTestSpeed(null);
                  setTestPitch(null);
                }}
              >
                <RotateCcw size={12} /> Về mặc định từng giọng
              </button>
            )}
          </div>
          <div className="form-grid">
            <div>
              <label className="form-label">
                Tốc độ đọc: <strong>{testSpeed !== null ? `${testSpeed.toFixed(2)}x` : 'Mặc định'}</strong>
              </label>
              <input
                type="range"
                min="0.82"
                max="1.32"
                step="0.02"
                style={{ width: '100%' }}
                value={testSpeed ?? 1.04}
                onChange={(e) => setTestSpeed(parseFloat(e.target.value))}
              />
            </div>
            <div>
              <label className="form-label">
                Độ trầm ấm (-5 Trầm dày → +5 Thanh sáng):{' '}
                <strong>{testPitch !== null ? testPitch.toFixed(1) : 'Mặc định'}</strong>
              </label>
              <input
                type="range"
                min="-5.0"
                max="5.0"
                step="0.4"
                style={{ width: '100%' }}
                value={testPitch ?? -0.8}
                onChange={(e) => setTestPitch(parseFloat(e.target.value))}
              />
            </div>
          </div>
        </div>

        {previewAudioUrl && (
          <div
            style={{
              marginBottom: 14,
              padding: '11px 14px',
              borderRadius: 8,
              background: 'var(--brand-soft)',
              border: '1px solid var(--brand-border)',
            }}
          >
            <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 6 }}>
              Đang phát: {activeVoiceName}
            </div>
            <audio controls autoPlay src={previewAudioUrl} style={{ width: '100%', height: 36 }} />
          </div>
        )}

        <div style={{ display: 'grid', gap: 8 }}>
          {voices.map((v) => (
            <div
              key={v.profile_id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                padding: '12px 14px',
                borderRadius: 9,
                background: 'var(--bg-input)',
                border: '1px solid var(--border)',
                flexWrap: 'wrap',
              }}
            >
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontWeight: 600, fontSize: 13.8 }}>
                  {stripLeadingEmoji(v.display_name)}
                </div>
                <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 2 }}>
                  Chuẩn {v.speed_rate}x • Độ trầm {v.pitch_hz > 0 ? `+${v.pitch_hz}` : v.pitch_hz} •{' '}
                  {v.emotion_prompt}
                </div>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                disabled={loadingPreviewId === v.profile_id}
                onClick={() => handlePreview(v)}
              >
                <Play size={14} /> {loadingPreviewId === v.profile_id ? 'Đang tạo...' : 'Nghe thử'}
              </button>
            </div>
          ))}
        </div>
      </div>

      <form className="card" onSubmit={handleCreateClone}>
        <div className="page-header">
          <div>
            <div className="page-title">
              <Mic size={19} strokeWidth={1.9} /> Nhân Bản Giọng Đọc Riêng Của Cửa Hàng (Voice Clone GPU)
            </div>
            <div className="page-subtitle">
              Tải tệp ghi âm mẫu 10–15 giây rõ chữ, không lẫn nhạc nền để tạo hồ sơ giọng riêng
            </div>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Tên gọi cho giọng đọc</label>
            <input
              className="input"
              placeholder="VD: Giọng Chủ Shop Tư Vấn Đàn"
              value={cloneName}
              onChange={(e) => setCloneName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Tốc độ đọc mặc định: {cloneSpeed}x</label>
            <input
              type="range"
              min="0.9"
              max="1.35"
              step="0.02"
              style={{ width: '100%', marginTop: 8 }}
              value={cloneSpeed}
              onChange={(e) => setCloneSpeed(parseFloat(e.target.value))}
            />
          </div>
        </div>

        <div className="form-group">
          <MediaDropzone
            accept="audio/*,video/*"
            icon={Upload}
            title={
              cloneFile
                ? `Đã chọn tệp mẫu: ${cloneFile.name}`
                : 'Kéo thả tệp ghi âm mẫu 10–15s (.mp3, .wav, .m4a, .mp4) hoặc bấm để chọn'
            }
            onFilesSelected={(files) => setCloneFile(files?.[0] || null)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Nội dung câu nói có trong đoạn ghi âm mẫu</label>
          <input
            className="input"
            placeholder="Gõ lại nguyên văn câu nói trong tệp ghi âm để tăng độ chính xác..."
            value={cloneRefText}
            onChange={(e) => setCloneRefText(e.target.value)}
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={savingClone}>
          <Plus size={15} /> {savingClone ? 'Đang xử lý mẫu giọng...' : 'Lưu giọng đọc mới'}
        </button>
      </form>
    </div>
  );
}
