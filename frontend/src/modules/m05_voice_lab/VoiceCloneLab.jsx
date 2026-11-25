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

function resolveVoiceCategoryBadge(v) {
  if (v.tier === 'LOCAL_F5_CLONE') return { label: 'Giọng thu riêng', cls: 'badge-warn' };
  if (v.tier === 'LOCAL_ONNX_VITS') return { label: 'Offline 0.1s', cls: 'badge-ok' };
  if (v.tier === 'GEMINI_EMOTIONAL') return { label: 'Diễn viên AI Studio', cls: 'badge-info' };
  if (v.dsp_preset === 'artisan_warm_studio' || v.dsp_preset === 'luxury_silk_female') {
    return { label: 'Nhạc cụ & Boutique', cls: 'badge-ok' };
  }
  return { label: 'Phim & Kể chuyện', cls: '' };
}

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
      notify('Đã lưu hồ sơ giọng đọc mới thành công.');
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
              <Volume2 size={20} strokeWidth={2} /> Kho {voices.length} Giọng Đọc Truyền Cảm & Phòng Nghe Thử
            </div>
            <div className="page-subtitle">
              So sánh trực quan từng chất giọng cho tư vấn nhạc cụ, thời trang và thuyết minh phim; tùy chỉnh tốc độ và độ trầm ấm ngay bên dưới
            </div>
          </div>
          <span className="badge badge-info">{voices.length} hồ sơ giọng</span>
        </div>

        {/* STEP 1: AUDITION BOX */}
        <div className="step-box">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Câu văn dùng để nghe thử & so sánh chất giọng:
            </label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
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
          </div>

          <textarea
            className="textarea"
            style={{ minHeight: 68, marginBottom: 12 }}
            value={sampleText}
            onChange={(e) => setSampleText(e.target.value)}
          />

          <div className="surface-box">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
              <strong style={{ fontSize: 13 }}>
                Tinh chỉnh Tốc độ & Độ trầm ấm khi bấm Nghe thử (Để mặc định sẽ theo chuẩn riêng từng giọng)
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
                  <RotateCcw size={12} /> Trả về mặc định từng giọng
                </button>
              )}
            </div>

            <div className="form-grid">
              <div>
                <div className="text-sub" style={{ fontSize: 12.2, marginBottom: 3 }}>
                  Tốc độ đọc thử:{' '}
                  <strong>{testSpeed !== null ? `${testSpeed.toFixed(2)}x` : 'Theo từng giọng'}</strong>
                </div>
                <input
                  type="range"
                  min="0.80"
                  max="1.35"
                  step="0.02"
                  style={{ width: '100%' }}
                  value={testSpeed ?? 1.04}
                  onChange={(e) => setTestSpeed(parseFloat(e.target.value))}
                />
              </div>
              <div>
                <div className="text-sub" style={{ fontSize: 12.2, marginBottom: 3 }}>
                  Độ trầm ấm thử:{' '}
                  <strong>
                    {testPitch !== null
                      ? `${testPitch > 0 ? `+${testPitch}` : testPitch} (Âm = trầm dày, Dương = thanh sáng)`
                      : 'Theo từng giọng'}
                  </strong>
                </div>
                <input
                  type="range"
                  min="-6.0"
                  max="6.0"
                  step="0.2"
                  style={{ width: '100%' }}
                  value={testPitch ?? 0.0}
                  onChange={(e) => setTestPitch(parseFloat(e.target.value))}
                />
              </div>
            </div>
          </div>

          {previewAudioUrl && (
            <div
              className="surface-box"
              style={{
                marginTop: 12,
                borderColor: 'var(--brand)',
                background: 'var(--brand-soft)',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                Đang phát thử: {activeVoiceName}
              </div>
              <audio controls autoPlay src={previewAudioUrl} style={{ width: '100%', height: 38 }} />
            </div>
          )}
        </div>

        {/* 2-COLUMN CLEAR VOICE GRID */}
        <div className="voice-library-grid">
          {voices.map((v) => {
            const cat = resolveVoiceCategoryBadge(v);
            const fullTitle = stripLeadingEmoji(v.display_name);
            const [shortName, roleDesc] = fullTitle.includes('—')
              ? fullTitle.split('—').map((s) => s.trim())
              : [fullTitle, ''];

            return (
              <div key={v.profile_id} className="voice-card-item">
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 5 }}>
                    <strong style={{ fontSize: 14.5 }}>{shortName}</strong>
                    <span className={`badge ${cat.cls}`} style={{ fontSize: 11 }}>
                      {cat.label}
                    </span>
                  </div>
                  {roleDesc && (
                    <div style={{ fontSize: 12.8, fontWeight: 600, color: 'var(--brand-text)', marginBottom: 4 }}>
                      {roleDesc}
                    </div>
                  )}
                  <div className="text-sub" style={{ fontSize: 12.2, lineHeight: 1.4 }}>
                    {v.emotion_prompt}
                  </div>
                </div>

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    paddingTop: 9,
                    borderTop: '1px solid var(--border)',
                    gap: 8,
                  }}
                >
                  <span className="text-muted" style={{ fontSize: 11.8 }}>
                    Chuẩn: <strong>{v.speed_rate}x</strong> • Độ trầm:{' '}
                    <strong>{v.pitch_hz > 0 ? `+${v.pitch_hz}` : v.pitch_hz}</strong>
                  </span>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={loadingPreviewId === v.profile_id}
                    onClick={() => handlePreview(v)}
                  >
                    <Play size={13} /> {loadingPreviewId === v.profile_id ? 'Đang tạo...' : 'Nghe thử'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* VOICE CLONE STUDIO CARD */}
      <form className="card" onSubmit={handleCreateClone}>
        <div className="page-header">
          <div>
            <div className="page-title">
              <Mic size={20} strokeWidth={2} /> Tạo Giọng Đọc Nhân Bản Từ Giọng Thật (Voice Clone GPU)
            </div>
            <div className="page-subtitle">
              Tải lên đoạn ghi âm 10–15 giây giọng thật rõ chữ (không lẫn nhạc nền) để thêm vào danh sách giọng đọc của cửa hàng
            </div>
          </div>
        </div>

        <div className="step-box" style={{ marginBottom: 14 }}>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Đặt tên gợi nhớ cho giọng đọc</label>
              <input
                className="input"
                placeholder="VD: Giọng Chủ Cửa Hàng Tư Vấn Đàn"
                value={cloneName}
                onChange={(e) => setCloneName(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Tốc độ đọc mặc định: <strong>{cloneSpeed}x</strong></label>
              <input
                type="range"
                min="0.90"
                max="1.30"
                step="0.02"
                style={{ width: '100%', marginTop: 10 }}
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
                  : 'Kéo thả tệp ghi âm mẫu 10–15 giây (.mp3, .wav, .m4a, .mp4) hoặc bấm để chọn'
              }
              hint="Nên thu ở nơi yên tĩnh để âm sắc nhân bản tự nhiên và rõ nét nhất"
              onFilesSelected={(files) => setCloneFile(files?.[0] || null)}
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Câu nói có trong tệp ghi âm mẫu (nhập nguyên văn để căn nhịp chuẩn)</label>
            <input
              className="input"
              placeholder="VD: Xin chào các bạn, hôm nay mình sẽ giới thiệu chi tiết mẫu đàn gỗ thịt tự nhiên này..."
              value={cloneRefText}
              onChange={(e) => setCloneRefText(e.target.value)}
            />
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={savingClone}>
          <Plus size={16} /> {savingClone ? 'Đang xử lý mẫu giọng...' : 'Lưu giọng đọc mới vào thư viện'}
        </button>
      </form>
    </div>
  );
}
