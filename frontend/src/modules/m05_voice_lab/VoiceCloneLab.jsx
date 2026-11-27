import React, { useState } from 'react';
import { Film, Headphones, Link2, Mic, Play, Plus, RotateCcw, Upload, Volume2 } from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import { stripLeadingEmoji } from '../m00_core_contracts/constants';
import { MediaDropzone } from '../m00_core_contracts/StudioWidgets';

const SAMPLE_PRESETS = [
  {
    label: 'Phim chiếu rạp Mỹ (Tín Hiệu Vô Hình)',
    text: 'Nhưng khi chính phủ chịu lắng nghe khoa học, thì nó đã quá muộn rồi. Đại dịch đã khiến xã hội ngưng lại đột ngột.',
  },
  {
    label: 'Hook Short TikTok 3 giây',
    text: 'Khoan lướt qua! Ba sai lầm mà chín mươi phần trăm người mới đều mắc phải ngay trong tuần đầu tiên mà không hề nhận ra.',
  },
  {
    label: 'Khoa học & Bí ẩn YouTube Shorts',
    text: 'Không ai ngờ rằng, sâu dưới lớp băng vĩnh cửu hàng vạn năm tuổi, các nhà khoa học vừa phát hiện một tín hiệu cổ xưa đầy bí ẩn.',
  },
  {
    label: 'Nghệ nhân chia sẻ đàn Violin',
    text: 'Điểm chạm cảm xúc đầu tiên của cây đàn này nằm ở mặt top gỗ thịt tự nhiên nguyên tấm, cho âm vang dày và ấm ngay từ nốt kéo đầu tiên.',
  },
];

const LAB_FILTER_TABS = [
  { id: 'ALL', label: 'Tất cả' },
  { id: 'MOVIE_DUB', label: 'Thuyết minh Phim' },
  { id: 'TIKTOK_SHORT', label: 'Short TikTok' },
  { id: 'YOUTUBE_SHORT', label: 'YouTube Shorts' },
  { id: 'ECOMMERCE_SALES', label: 'Tư vấn Bán hàng' },
  { id: 'OFFLINE_ONLY', label: 'Offline 0.1s' },
  { id: 'CLONED_ONLY', label: 'Giọng thu / YouTube' },
];

const CATEGORY_BADGES = {
  MOVIE_DUB: { label: 'Thuyết minh Phim', cls: 'badge-warn' },
  TIKTOK_SHORT: { label: 'Short TikTok', cls: 'badge-info' },
  YOUTUBE_SHORT: { label: 'YouTube Shorts', cls: 'badge-ok' },
  ECOMMERCE_SALES: { label: 'Bán hàng & Showroom', cls: 'badge-ok' },
};

function resolveVoiceCategoryBadge(v) {
  if (v.tier === 'LOCAL_F5_CLONE') return { label: 'Mẫu YouTube / Thu riêng', cls: 'badge-warn' };
  if (v.tier === 'LOCAL_ONNX_VITS') {
    const base = CATEGORY_BADGES[v.category] || { label: 'Đa năng', cls: 'badge-ok' };
    return { label: `${base.label} • Offline 0.1s`, cls: 'badge-ok' };
  }
  return CATEGORY_BADGES[v.category] || { label: 'Thuyết minh Phim', cls: 'badge-info' };
}

export default function VoiceCloneLab({ voices, onVoicesChanged, notify }) {
  const [sampleText, setSampleText] = useState(SAMPLE_PRESETS[0].text);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [testSpeed, setTestSpeed] = useState(null);
  const [testPitch, setTestPitch] = useState(null);
  const [previewAudioUrl, setPreviewAudioUrl] = useState('');
  const [activeVoiceName, setActiveVoiceName] = useState('');
  const [loadingPreviewId, setLoadingPreviewId] = useState('');

  // Clone Mode ('YOUTUBE' | 'UPLOAD')
  const [cloneSourceMode, setCloneSourceMode] = useState('YOUTUBE');

  // YouTube Clone state
  const [ytUrl, setYtUrl] = useState('');
  const [ytVoiceName, setYtVoiceName] = useState('');
  const [ytStartSec, setYtStartSec] = useState(5);
  const [ytDurationSec, setYtDurationSec] = useState(15);
  const [ytCategory, setYtCategory] = useState('MOVIE_DUB');
  const [ytDialect, setYtDialect] = useState('auto');
  const [ytSpeed, setYtSpeed] = useState(1.02);
  const [ytRefText, setYtRefText] = useState('');
  const [cloningYoutube, setCloningYoutube] = useState(false);

  // Local Upload Clone state
  const [cloneName, setCloneName] = useState('');
  const [cloneRefText, setCloneRefText] = useState('');
  const [cloneSpeed, setCloneSpeed] = useState(1.04);
  const [cloneCategory, setCloneCategory] = useState('MOVIE_DUB');
  const [cloneDialect, setCloneDialect] = useState('auto');
  const [cloneFile, setCloneFile] = useState(null);
  const [savingClone, setSavingClone] = useState(false);

  const matchesFilter = (v, tabId) => {
    if (tabId === 'ALL') return true;
    if (tabId === 'OFFLINE_ONLY') return v.tier === 'LOCAL_ONNX_VITS';
    if (tabId === 'CLONED_ONLY') return v.tier === 'LOCAL_F5_CLONE';
    return (v.category || 'MOVIE_DUB') === tabId;
  };

  const filteredVoices = voices.filter((v) => matchesFilter(v, activeFilter));

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

  const handlePlayOriginalSample = (voiceObj) => {
    if (!voiceObj.sample_audio_url) return;
    setActiveVoiceName(`Mẫu gốc trích xuất: ${stripLeadingEmoji(voiceObj.display_name)}`);
    setPreviewAudioUrl(`${voiceObj.sample_audio_url}?t=${Date.now()}`);
  };

  const handleYoutubeCloneSubmit = async (e) => {
    e.preventDefault();
    if (!ytUrl.trim() || !ytVoiceName.trim()) {
      notify('Vui lòng dán link YouTube và đặt tên cho giọng thuyết minh mới.');
      return;
    }
    setCloningYoutube(true);
    try {
      const created = await studioApi.cloneVoiceFromYoutube({
        youtube_url: ytUrl.trim(),
        display_name: ytVoiceName.trim(),
        start_sec: Number(ytStartSec) || 5,
        duration_sec: Number(ytDurationSec) || 15,
        category: ytCategory,
        dialect_hint: ytDialect,
        speed_rate: Number(ytSpeed) || 1.02,
        sample_ref_text: ytRefText.trim(),
      });
      setYtVoiceName('');
      setYtRefText('');
      await onVoicesChanged();
      setActiveFilter('CLONED_ONLY');
      if (created?.sample_audio_url) {
        setActiveVoiceName(`Mẫu gốc vừa tách: ${created.display_name}`);
        setPreviewAudioUrl(`${created.sample_audio_url}?t=${Date.now()}`);
      }
      notify('Đã tách mẫu giọng sạch từ YouTube, nhận diện lời thoại bằng GPU và lưu vào thư viện!');
    } catch (err) {
      notify(`Không thể tách giọng từ YouTube: ${err.message}`);
    } finally {
      setCloningYoutube(false);
    }
  };

  const handleCreateClone = async (e) => {
    e.preventDefault();
    if (!cloneName.trim() || !cloneFile) {
      notify('Vui lòng đặt tên giọng và chọn tệp âm thanh mẫu (10–20 giây).');
      return;
    }
    setSavingClone(true);
    try {
      const fd = new FormData();
      fd.append('display_name', cloneName.trim());
      fd.append('sample_ref_text', cloneRefText);
      fd.append('speed_rate', String(cloneSpeed));
      fd.append('category', cloneCategory);
      fd.append('dialect_hint', cloneDialect);
      fd.append('sample_file', cloneFile);
      await studioApi.uploadCloneVoice(fd);
      setCloneName('');
      setCloneRefText('');
      setCloneFile(null);
      await onVoicesChanged();
      setActiveFilter('CLONED_ONLY');
      notify('Đã phân tích âm sắc và lưu hồ sơ giọng đọc mới thành công.');
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
              <Volume2 size={20} strokeWidth={2} /> Kho {voices.length} Giọng Đọc Phân Nhóm Theo Nền Tảng
            </div>
            <div className="page-subtitle">
              Phân loại rõ ràng cho Short TikTok, YouTube Shorts, Thuyết minh Phim Chiếu Rạp (USLT) và Tư vấn Bán hàng
            </div>
          </div>
          <span className="badge badge-info">{voices.length} hồ sơ giọng</span>
        </div>

        {/* STEP 1: AUDITION BOX */}
        <div className="step-box">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 8,
              flexWrap: 'wrap',
              marginBottom: 8,
            }}
          >
            <label className="form-label" style={{ marginBottom: 0 }}>
              Câu văn mẫu để nghe thử & so sánh chất giọng:
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
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 8,
                flexWrap: 'wrap',
                gap: 6,
              }}
            >
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
                Đang phát: {activeVoiceName}
              </div>
              <audio controls autoPlay src={previewAudioUrl} style={{ width: '100%', height: 38 }} />
            </div>
          )}
        </div>

        {/* PLATFORM CATEGORY FILTER BAR */}
        <div
          style={{
            display: 'flex',
            gap: 6,
            flexWrap: 'wrap',
            marginBottom: 14,
            paddingBottom: 10,
            borderBottom: '1px solid var(--border)',
          }}
        >
          {LAB_FILTER_TABS.map((tab) => {
            const count = voices.filter((v) => matchesFilter(v, tab.id)).length;
            const active = activeFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                className={`btn btn-sm ${active ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setActiveFilter(tab.id)}
              >
                {tab.label} ({count})
              </button>
            );
          })}
        </div>

        {/* 2-COLUMN CLEAR VOICE GRID */}
        <div className="voice-library-grid">
          {filteredVoices.map((v) => {
            const cat = resolveVoiceCategoryBadge(v);
            const fullTitle = stripLeadingEmoji(v.display_name);
            const [shortName, roleDesc] = fullTitle.includes('—')
              ? fullTitle.split('—').map((s) => s.trim())
              : [fullTitle, ''];

            return (
              <div key={v.profile_id} className="voice-card-item">
                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'flex-start',
                      gap: 8,
                      marginBottom: 5,
                    }}
                  >
                    <strong style={{ fontSize: 14.5 }}>{shortName}</strong>
                    <span className={`badge ${cat.cls}`} style={{ fontSize: 11 }}>
                      {cat.label}
                    </span>
                  </div>
                  {roleDesc && (
                    <div
                      style={{
                        fontSize: 12.8,
                        fontWeight: 600,
                        color: 'var(--brand-text)',
                        marginBottom: 5,
                      }}
                    >
                      {roleDesc}
                    </div>
                  )}
                  {Array.isArray(v.tags) && v.tags.length > 0 && (
                    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 6 }}>
                      {v.tags.map((tg, idx) => (
                        <span
                          key={idx}
                          className="badge"
                          style={{ fontSize: 10.5, padding: '2px 7px' }}
                        >
                          {tg}
                        </span>
                      ))}
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
                    flexWrap: 'wrap',
                  }}
                >
                  <span className="text-muted" style={{ fontSize: 11.8 }}>
                    Chuẩn: <strong>{v.speed_rate}x</strong> • Độ trầm:{' '}
                    <strong>{v.pitch_hz > 0 ? `+${v.pitch_hz}` : v.pitch_hz}</strong>
                  </span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {v.sample_audio_url && (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        title="Nghe đoạn giọng gốc trích xuất từ phim/tệp mẫu"
                        onClick={() => handlePlayOriginalSample(v)}
                      >
                        <Headphones size={13} /> Mẫu gốc
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={loadingPreviewId === v.profile_id}
                      onClick={() => handlePreview(v)}
                    >
                      <Play size={13} /> {loadingPreviewId === v.profile_id ? 'Đang tạo...' : 'Nghe thử'}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* VOICE CLONE STUDIO CARD (YOUTUBE URL + LOCAL UPLOAD) */}
      <div className="card">
        <div className="page-header">
          <div>
            <div className="page-title">
              <Mic size={20} strokeWidth={2} /> Tách & Nhái Giọng Thuyết Minh Từ Phim YouTube Hoặc Tệp Thu Âm
            </div>
            <div className="page-subtitle">
              Dán thẳng link phim YouTube yêu thích (hệ thống tự cắt đoạn, khử nhiễu nền & quét giọng bằng GPU RTX 3060) hoặc tải lên tệp thu âm riêng
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`btn ${cloneSourceMode === 'YOUTUBE' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setCloneSourceMode('YOUTUBE')}
          >
            <Link2 size={15} /> Tách & Nhái Giọng Từ Link YouTube
          </button>
          <button
            type="button"
            className={`btn ${cloneSourceMode === 'UPLOAD' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setCloneSourceMode('UPLOAD')}
          >
            <Upload size={15} /> Tải Lên Tệp Ghi Âm Có Sẵn (.mp3, .wav, .mp4)
          </button>
        </div>

        {cloneSourceMode === 'YOUTUBE' ? (
          <form onSubmit={handleYoutubeCloneSubmit}>
            <div className="step-box" style={{ marginBottom: 14 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  flexWrap: 'wrap',
                  marginBottom: 8,
                }}
              >
                <label className="form-label" style={{ marginBottom: 0 }}>
                  Liên kết video YouTube có giọng thuyết minh bạn muốn lấy mẫu
                </label>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setYtUrl('https://www.youtube.com/watch?v=3s-dbpC0PRc');
                    setYtVoiceName('Nữ Thuyết Minh Tín Hiệu Vô Hình');
                    setYtStartSec(5);
                    setYtDurationSec(16);
                    setYtCategory('MOVIE_DUB');
                    setYtDialect('nam');
                  }}
                >
                  <Film size={13} /> Điền nhanh phim mẫu Tín Hiệu Vô Hình
                </button>
              </div>

              <div className="form-group">
                <input
                  className="input"
                  placeholder="VD: https://www.youtube.com/watch?v=3s-dbpC0PRc"
                  value={ytUrl}
                  onChange={(e) => setYtUrl(e.target.value)}
                />
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Đặt tên cho giọng đọc mới</label>
                  <input
                    className="input"
                    placeholder="VD: Nữ Thuyết Minh Chiếu Rạp USLT"
                    value={ytVoiceName}
                    onChange={(e) => setYtVoiceName(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Xếp vào nhóm sử dụng</label>
                  <select
                    className="select"
                    value={ytCategory}
                    onChange={(e) => setYtCategory(e.target.value)}
                  >
                    <option value="MOVIE_DUB">Lồng tiếng & Thuyết minh Phim</option>
                    <option value="TIKTOK_SHORT">Chuyên Short TikTok</option>
                    <option value="YOUTUBE_SHORT">Chuyên YouTube Shorts</option>
                    <option value="ECOMMERCE_SALES">Tư vấn Bán hàng & Showroom</option>
                  </select>
                </div>
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Cắt mẫu từ giây thứ (chọn đoạn đang có lời thuyết minh)</label>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="number"
                      className="input"
                      min={0}
                      max={14000}
                      value={ytStartSec}
                      onChange={(e) => setYtStartSec(e.target.value)}
                    />
                    <span className="text-sub" style={{ whiteSpace: 'nowrap' }}>
                      Độ dài (giây):
                    </span>
                    <input
                      type="number"
                      className="input"
                      style={{ width: 92 }}
                      min={6}
                      max={22}
                      value={ytDurationSec}
                      onChange={(e) => setYtDurationSec(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Phương ngữ & tốc độ mặc định ({Number(ytSpeed).toFixed(2)}x)
                  </label>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <select
                      className="select"
                      value={ytDialect}
                      onChange={(e) => setYtDialect(e.target.value)}
                    >
                      <option value="auto">Tự nhận diện vùng miền</option>
                      <option value="nam">Giọng Miền Nam (Sài Gòn / USLT)</option>
                      <option value="bac">Giọng Miền Bắc (Hà Nội / VTV)</option>
                    </select>
                    <input
                      type="range"
                      min="0.90"
                      max="1.25"
                      step="0.02"
                      style={{ width: 120 }}
                      value={ytSpeed}
                      onChange={(e) => setYtSpeed(parseFloat(e.target.value))}
                    />
                  </div>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
                  Câu thoại mẫu (Tùy chọn — Để trống GPU Faster-Whisper sẽ tự nghe và điền giúp bạn)
                </label>
                <input
                  className="input"
                  placeholder="Để trống để hệ thống tự động nhận diện lời thoại tiếng Việt trong đoạn cắt..."
                  value={ytRefText}
                  onChange={(e) => setYtRefText(e.target.value)}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={cloningYoutube}>
              <Plus size={16} />{' '}
              {cloningYoutube
                ? 'Đang tải đoạn mẫu YouTube, lọc nhiễu & phân tích giọng trên GPU...'
                : 'Tự động tách mẫu YouTube & Lưu vào kho giọng'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleCreateClone}>
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
                  <label className="form-label">Xếp vào nhóm & vùng miền</label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <select
                      className="select"
                      value={cloneCategory}
                      onChange={(e) => setCloneCategory(e.target.value)}
                    >
                      <option value="MOVIE_DUB">Thuyết minh Phim</option>
                      <option value="TIKTOK_SHORT">Short TikTok</option>
                      <option value="YOUTUBE_SHORT">YouTube Shorts</option>
                      <option value="ECOMMERCE_SALES">Tư vấn Bán hàng</option>
                    </select>
                    <select
                      className="select"
                      style={{ width: 155 }}
                      value={cloneDialect}
                      onChange={(e) => setCloneDialect(e.target.value)}
                    >
                      <option value="auto">Tự động</option>
                      <option value="nam">Miền Nam</option>
                      <option value="bac">Miền Bắc</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">
                  Tốc độ đọc mặc định: <strong>{cloneSpeed}x</strong>
                </label>
                <input
                  type="range"
                  min="0.90"
                  max="1.30"
                  step="0.02"
                  style={{ width: '100%' }}
                  value={cloneSpeed}
                  onChange={(e) => setCloneSpeed(parseFloat(e.target.value))}
                />
              </div>

              <div className="form-group">
                <MediaDropzone
                  accept="audio/*,video/*"
                  icon={Upload}
                  title={
                    cloneFile
                      ? `Đã chọn tệp mẫu: ${cloneFile.name}`
                      : 'Kéo thả tệp ghi âm mẫu 10–20 giây (.mp3, .wav, .m4a, .mp4) hoặc bấm để chọn'
                  }
                  hint="Hệ thống tự khử nhiễu phòng thu và nhận diện lời thoại bằng GPU nếu bạn để trống câu mẫu"
                  onFilesSelected={(files) => setCloneFile(files?.[0] || null)}
                />
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
                  Câu nói trong tệp mẫu (Tùy chọn — Để trống hệ thống tự nhận diện bằng GPU)
                </label>
                <input
                  className="input"
                  placeholder="Để trống để GPU tự động chép lời, hoặc nhập nguyên văn câu mẫu..."
                  value={cloneRefText}
                  onChange={(e) => setCloneRefText(e.target.value)}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" disabled={savingClone}>
              <Plus size={16} />{' '}
              {savingClone ? 'Đang xử lý & phân tích mẫu giọng...' : 'Lưu giọng đọc mới vào thư viện'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
