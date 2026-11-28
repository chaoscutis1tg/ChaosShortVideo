import React, { useRef, useState } from 'react';
import {
  ArrowLeft,
  Film,
  Headphones,
  Link2,
  Loader2,
  Mic,
  Play,
  Plus,
  RotateCcw,
  SlidersHorizontal,
  Upload,
  Volume2,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import { stripLeadingEmoji } from '../m00_core_contracts/constants';
import {
  FieldError,
  hasAllowedExtension,
  isValidHttpUrl,
  MediaDropzone,
  scrollToFirstValidationError,
  StudioCollapsible,
  StudioLoadingBanner,
  StudioPageHeader,
} from '../m00_core_contracts/StudioWidgets';

const SAMPLE_PRESETS = [
  {
    label: 'Phim chiếu rạp Mỹ',
    text: 'Nhưng khi chính phủ chịu lắng nghe khoa học, thì nó đã quá muộn rồi. Đại dịch đã khiến xã hội ngưng lại đột ngột.',
  },
  {
    label: 'Hook Short TikTok 3s',
    text: 'Khoan lướt qua! Ba sai lầm mà chín mươi phần trăm người mới đều mắc phải ngay trong tuần đầu tiên mà không hề nhận ra.',
  },
  {
    label: 'Khoa học YouTube Shorts',
    text: 'Không ai ngờ rằng, sâu dưới lớp băng vĩnh cửu hàng vạn năm tuổi, các nhà khoa học vừa phát hiện một tín hiệu cổ xưa đầy bí ẩn.',
  },
  {
    label: 'Nghệ nhân tư vấn Violin',
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

export default function VoiceCloneLab({ voices, onVoicesChanged, onBackToStudio, notify }) {
  const [activeSection, setActiveSection] = useState('LIBRARY');
  const [sampleText, setSampleText] = useState(SAMPLE_PRESETS[0].text);
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [testSpeed, setTestSpeed] = useState(null);
  const [testPitch, setTestPitch] = useState(null);
  const [previewAudioUrl, setPreviewAudioUrl] = useState('');
  const [activeVoiceName, setActiveVoiceName] = useState('');
  const [loadingPreviewId, setLoadingPreviewId] = useState('');

  const [cloneSourceMode, setCloneSourceMode] = useState('YOUTUBE');

  const [ytUrl, setYtUrl] = useState('');
  const [ytVoiceName, setYtVoiceName] = useState('');
  const [ytStartSec, setYtStartSec] = useState(5);
  const [ytDurationSec, setYtDurationSec] = useState(15);
  const [ytCategory, setYtCategory] = useState('MOVIE_DUB');
  const [ytDialect, setYtDialect] = useState('auto');
  const [ytSpeed, setYtSpeed] = useState(1.02);
  const [ytRefText, setYtRefText] = useState('');
  const [cloningYoutube, setCloningYoutube] = useState(false);

  const [cloneName, setCloneName] = useState('');
  const [cloneRefText, setCloneRefText] = useState('');
  const [cloneSpeed, setCloneSpeed] = useState(1.04);
  const [cloneCategory, setCloneCategory] = useState('MOVIE_DUB');
  const [cloneDialect, setCloneDialect] = useState('auto');
  const [cloneFile, setCloneFile] = useState(null);
  const [savingClone, setSavingClone] = useState(false);
  const [errors, setErrors] = useState({});
  const cloneCardRef = useRef(null);

  const clearError = (...keys) => {
    setErrors((prev) => {
      let changed = false;
      const next = { ...prev };
      keys.forEach((k) => {
        if (next[k]) {
          delete next[k];
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  };

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
        `${stripLeadingEmoji(voiceObj.display_name)} (${spd.toFixed(2)}x, độ trầm ${
          ptc > 0 ? `+${ptc}` : ptc
        })`
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
    const cleanUrl = ytUrl.trim();
    const cleanName = ytVoiceName.trim();
    const startNum = Number(ytStartSec);
    const durNum = Number(ytDurationSec);
    const nextErrs = {};

    if (!isValidHttpUrl(cleanUrl)) {
      nextErrs.ytUrl =
        'Vui lòng dán đường dẫn video YouTube hợp lệ (bắt đầu bằng https://www.youtube.com/... hoặc https://youtu.be/...).';
    }
    if (cleanName.length < 2 || cleanName.length > 80) {
      nextErrs.ytVoiceName = 'Tên giọng đọc mới cần từ 2 đến 80 ký tự.';
    }
    if (!Number.isFinite(startNum) || startNum < 0 || startNum > 14400) {
      nextErrs.ytTiming = 'Giây bắt đầu cắt mẫu phải nằm trong khoảng 0 – 14.400 giây.';
    } else if (!Number.isFinite(durNum) || durNum < 6 || durNum > 22) {
      nextErrs.ytTiming = 'Độ dài đoạn giọng mẫu cần từ 6 đến 22 giây để đạt độ chuẩn cao nhất.';
    }

    if (Object.keys(nextErrs).length > 0) {
      setErrors(nextErrs);
      scrollToFirstValidationError(cloneCardRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    setErrors({});
    setCloningYoutube(true);
    try {
      const created = await studioApi.cloneVoiceFromYoutube({
        youtube_url: cleanUrl,
        display_name: cleanName,
        start_sec: Math.round(startNum),
        duration_sec: Math.round(durNum),
        category: ytCategory,
        dialect_hint: ytDialect,
        speed_rate: Number(ytSpeed) || 1.02,
        sample_ref_text: ytRefText.trim(),
      });
      setYtVoiceName('');
      setYtRefText('');
      await onVoicesChanged();
      setActiveSection('LIBRARY');
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
    const cleanName = cloneName.trim();
    const nextErrs = {};
    if (cleanName.length < 2 || cleanName.length > 80) {
      nextErrs.cloneName = 'Vui lòng đặt tên gợi nhớ cho giọng đọc (2 – 80 ký tự).';
    }
    if (!cloneFile) {
      nextErrs.cloneFile = 'Vui lòng chọn tệp ghi âm mẫu (.mp3, .wav, .m4a, .mp4) dài 6 – 22 giây.';
    } else if (
      !hasAllowedExtension(cloneFile.name, ['.mp3', '.wav', '.m4a', '.flac', '.ogg', '.mp4', '.mov'])
    ) {
      nextErrs.cloneFile = 'Định dạng tệp mẫu chưa hợp lệ (.mp3, .wav, .m4a, .flac, .mp4).';
    }

    if (Object.keys(nextErrs).length > 0) {
      setErrors(nextErrs);
      scrollToFirstValidationError(cloneCardRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    setErrors({});
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
      setActiveSection('LIBRARY');
      setActiveFilter('CLONED_ONLY');
      notify('Đã phân tích âm sắc và lưu hồ sơ giọng đọc mới thành công.');
    } catch (err) {
      notify(`Không thể tạo giọng mẫu: ${err.message}`);
    } finally {
      setSavingClone(false);
    }
  };

  return (
    <div className="card" ref={cloneCardRef}>
      <StudioPageHeader
        icon={Volume2}
        title={`Phòng Giọng Đọc & Nhân Bản Âm Sắc (${voices.length} giọng)`}
        subtitle="Nghe thử, so sánh chất giọng theo từng nền tảng (TikTok, Shorts, Phim rạp, Bán hàng) hoặc tách giọng từ YouTube"
        badges={[{ label: `${voices.length} hồ sơ giọng`, cls: 'badge-info' }]}
        actions={
          onBackToStudio ? (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onBackToStudio}>
              <ArrowLeft size={14} /> Quay lại xưởng dựng
            </button>
          ) : null
        }
      />

      {/* CLEAN 2-SECTION SEGMENTED BAR */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
          marginBottom: 20,
        }}
      >
        <div className="studio-segmented">
          <button
            type="button"
            className={`studio-seg-btn ${activeSection === 'LIBRARY' ? 'active' : ''}`}
            onClick={() => setActiveSection('LIBRARY')}
          >
            <Volume2 size={15} /> Kho giọng &amp; Nghe thử ({voices.length})
          </button>
          <button
            type="button"
            className={`studio-seg-btn ${activeSection === 'CLONE' ? 'active' : ''}`}
            onClick={() => setActiveSection('CLONE')}
          >
            <Mic size={15} /> Tách &amp; Nhân bản giọng mới
          </button>
        </div>
      </div>

      {activeSection === 'LIBRARY' ? (
        <div className="fade-slide-in">
          {/* AUDITION BOX */}
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
                Câu văn mẫu để nghe thử &amp; so sánh chất giọng
              </label>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {SAMPLE_PRESETS.map((sp, i) => (
                  <button
                    key={i}
                    type="button"
                    className="filter-pill"
                    onClick={() => setSampleText(sp.text)}
                  >
                    {sp.label}
                  </button>
                ))}
              </div>
            </div>

            <textarea
              className="textarea"
              style={{ minHeight: 70 }}
              value={sampleText}
              onChange={(e) => setSampleText(e.target.value)}
            />

            <StudioCollapsible
              icon={SlidersHorizontal}
              title="Tinh chỉnh Tốc độ & Độ trầm ấm khi nghe thử"
              subtitle="Để mặc định sẽ phát theo thông số chuẩn riêng của từng giọng"
              badge={testSpeed !== null || testPitch !== null ? 'Đang tùy chỉnh' : ''}
            >
              <div className="form-grid">
                <div>
                  <div className="text-xs text-sub" style={{ marginBottom: 4 }}>
                    Tốc độ đọc thử:{' '}
                    <strong>
                      {testSpeed !== null ? `${testSpeed.toFixed(2)}x` : 'Theo từng giọng'}
                    </strong>
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
                  <div className="text-xs text-sub" style={{ marginBottom: 4 }}>
                    Độ trầm ấm thử:{' '}
                    <strong>
                      {testPitch !== null
                        ? `${testPitch > 0 ? `+${testPitch}` : testPitch}`
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
              {(testSpeed !== null || testPitch !== null) && (
                <div style={{ marginTop: 10 }}>
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
                </div>
              )}
            </StudioCollapsible>

            {previewAudioUrl && (
              <div className="studio-callout studio-callout-brand fade-slide-in" style={{ marginTop: 14 }}>
                <div className="text-sm fw-600" style={{ marginBottom: 6 }}>
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
              marginBottom: 16,
            }}
          >
            {LAB_FILTER_TABS.map((tab) => {
              const count = voices.filter((v) => matchesFilter(v, tab.id)).length;
              const active = activeFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  className={`filter-pill ${active ? 'active' : ''}`}
                  onClick={() => setActiveFilter(tab.id)}
                >
                  {tab.label} ({count})
                </button>
              );
            })}
          </div>

          {/* VOICE CARDS GRID */}
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
                        marginBottom: 6,
                      }}
                    >
                      <strong className="text-md">{shortName}</strong>
                      <span className={`badge ${cat.cls}`}>{cat.label}</span>
                    </div>
                    {roleDesc && (
                      <div className="text-xs fw-600 text-brand" style={{ marginBottom: 6 }}>
                        {roleDesc}
                      </div>
                    )}
                    {Array.isArray(v.tags) && v.tags.length > 0 && (
                      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 8 }}>
                        {v.tags.map((tg, idx) => (
                          <span key={idx} className="badge">
                            {tg}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="text-xs text-sub">{v.emotion_prompt}</div>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      paddingTop: 10,
                      borderTop: '1px solid var(--border)',
                      gap: 8,
                      flexWrap: 'wrap',
                    }}
                  >
                    <span className="text-xs text-muted">
                      Chuẩn: <strong>{v.speed_rate}x</strong> • Độ trầm:{' '}
                      <strong>{v.pitch_hz > 0 ? `+${v.pitch_hz}` : v.pitch_hz}</strong>
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {v.sample_audio_url && (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
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
                        {loadingPreviewId === v.profile_id ? (
                          <Loader2 size={13} className="spin" />
                        ) : (
                          <Play size={13} />
                        )}
                        <span>{loadingPreviewId === v.profile_id ? 'Đang tạo...' : 'Nghe thử'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="step-box fade-slide-in" style={{ marginBottom: 0 }}>
          <div className="step-header">
            <span className="step-num">
              <Mic size={14} />
            </span>
            <div style={{ flex: 1 }}>
              <div className="step-title">Tách &amp; Nhân bản giọng đọc từ YouTube hoặc Tệp thu âm</div>
              <div className="step-desc">
                Hệ thống tự cắt đoạn mẫu 6–22 giây, khử nhiễu phòng thu và nhận diện lời thoại bằng GPU
              </div>
            </div>

            <div className="studio-segmented">
              <button
                type="button"
                className={`studio-seg-btn ${cloneSourceMode === 'YOUTUBE' ? 'active' : ''}`}
                onClick={() => setCloneSourceMode('YOUTUBE')}
              >
                <Link2 size={14} /> Từ Link YouTube
              </button>
              <button
                type="button"
                className={`studio-seg-btn ${cloneSourceMode === 'UPLOAD' ? 'active' : ''}`}
                onClick={() => setCloneSourceMode('UPLOAD')}
              >
                <Upload size={14} /> Tải tệp ghi âm
              </button>
            </div>
          </div>

          {cloneSourceMode === 'YOUTUBE' ? (
            <form onSubmit={handleYoutubeCloneSubmit}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  flexWrap: 'wrap',
                  marginBottom: 6,
                }}
              >
                <label className="form-label" style={{ marginBottom: 0 }}>
                  Liên kết video YouTube có giọng thuyết minh mẫu
                </label>
                <button
                  type="button"
                  className="filter-pill"
                  onClick={() => {
                    setYtUrl('https://www.youtube.com/watch?v=3s-dbpC0PRc');
                    setYtVoiceName('Nữ Thuyết Minh Tín Hiệu Vô Hình');
                    setYtStartSec(5);
                    setYtDurationSec(16);
                    setYtCategory('MOVIE_DUB');
                    setYtDialect('nam');
                  }}
                >
                  <Film size={12} /> Điền nhanh mẫu thử
                </button>
              </div>

              <div className="form-group">
                <input
                  className={`input ${errors.ytUrl ? 'input-error' : ''}`}
                  placeholder="VD: https://www.youtube.com/watch?v=..."
                  value={ytUrl}
                  onChange={(e) => {
                    setYtUrl(e.target.value);
                    clearError('ytUrl');
                  }}
                />
                <FieldError message={errors.ytUrl} />
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Đặt tên cho giọng đọc mới</label>
                  <input
                    className={`input ${errors.ytVoiceName ? 'input-error' : ''}`}
                    placeholder="VD: Nữ Thuyết Minh Chiếu Rạp USLT"
                    value={ytVoiceName}
                    onChange={(e) => {
                      setYtVoiceName(e.target.value);
                      clearError('ytVoiceName');
                    }}
                  />
                  <FieldError message={errors.ytVoiceName} />
                </div>
                <div className="form-group">
                  <label className="form-label">Xếp vào nhóm sử dụng</label>
                  <select
                    className="select"
                    value={ytCategory}
                    onChange={(e) => setYtCategory(e.target.value)}
                  >
                    <option value="MOVIE_DUB">Lồng tiếng &amp; Thuyết minh Phim</option>
                    <option value="TIKTOK_SHORT">Chuyên Short TikTok</option>
                    <option value="YOUTUBE_SHORT">Chuyên YouTube Shorts</option>
                    <option value="ECOMMERCE_SALES">Tư vấn Bán hàng &amp; Showroom</option>
                  </select>
                </div>
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Giây bắt đầu cắt mẫu &amp; Độ dài (6 – 22 giây)</label>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="number"
                      className={`input ${errors.ytTiming ? 'input-error' : ''}`}
                      min={0}
                      max={14000}
                      value={ytStartSec}
                      onChange={(e) => {
                        setYtStartSec(e.target.value);
                        clearError('ytTiming');
                      }}
                    />
                    <span className="text-xs text-sub" style={{ whiteSpace: 'nowrap' }}>
                      Độ dài (s):
                    </span>
                    <input
                      type="number"
                      className={`input ${errors.ytTiming ? 'input-error' : ''}`}
                      style={{ width: 96 }}
                      min={6}
                      max={22}
                      value={ytDurationSec}
                      onChange={(e) => {
                        setYtDurationSec(e.target.value);
                        clearError('ytTiming');
                      }}
                    />
                  </div>
                  <FieldError message={errors.ytTiming} />
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Phương ngữ &amp; tốc độ mặc định ({Number(ytSpeed).toFixed(2)}x)
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

              <div className="form-group">
                <label className="form-label">
                  Câu thoại mẫu (Để trống GPU Faster-Whisper tự nghe và điền)
                </label>
                <input
                  className="input"
                  placeholder="Để trống để hệ thống tự động nhận diện lời thoại tiếng Việt..."
                  value={ytRefText}
                  onChange={(e) => setYtRefText(e.target.value)}
                />
              </div>

              <StudioLoadingBanner
                loading={cloningYoutube}
                title="Đang tải đoạn mẫu YouTube, khử nhiễu nền & nhận diện giọng đọc trên GPU..."
                subtitle="Quá trình thường mất 10 – 20 giây để tạo hồ sơ âm sắc chuẩn phòng thu"
                steps={[
                  'Tải & cắt đoạn âm thanh từ YouTube',
                  'Khử nhiễu nền & chuẩn hóa âm lượng',
                  'Nhận diện lời thoại bằng GPU Faster-Whisper',
                ]}
                stepIntervalMs={3200}
              />

              <button type="submit" className="btn btn-primary" disabled={cloningYoutube}>
                {cloningYoutube ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
                <span>
                  {cloningYoutube
                    ? 'Đang phân tích giọng trên GPU...'
                    : 'Tách mẫu YouTube & Lưu vào kho giọng'}
                </span>
              </button>
            </form>
          ) : (
            <form onSubmit={handleCreateClone}>
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Đặt tên gợi nhớ cho giọng đọc</label>
                  <input
                    className={`input ${errors.cloneName ? 'input-error' : ''}`}
                    placeholder="VD: Giọng Chủ Cửa Hàng Tư Vấn Đàn"
                    value={cloneName}
                    onChange={(e) => {
                      setCloneName(e.target.value);
                      clearError('cloneName');
                    }}
                  />
                  <FieldError message={errors.cloneName} />
                </div>
                <div className="form-group">
                  <label className="form-label">Xếp vào nhóm &amp; vùng miền</label>
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
                  loading={savingClone}
                  error={errors.cloneFile}
                  title={
                    cloneFile
                      ? `Đã chọn tệp mẫu: ${cloneFile.name}`
                      : 'Kéo thả tệp ghi âm mẫu 10–20 giây (.mp3, .wav, .m4a, .mp4) hoặc bấm để chọn'
                  }
                  hint="Hệ thống tự khử nhiễu phòng thu và nhận diện lời thoại bằng GPU nếu bạn để trống câu mẫu"
                  onFilesSelected={(files) => {
                    setCloneFile(files?.[0] || null);
                    clearError('cloneFile');
                  }}
                />
              </div>

              <div className="form-group">
                <label className="form-label">
                  Câu nói trong tệp mẫu (Để trống hệ thống tự nhận diện bằng GPU)
                </label>
                <input
                  className="input"
                  placeholder="Để trống để GPU tự động chép lời..."
                  value={cloneRefText}
                  onChange={(e) => setCloneRefText(e.target.value)}
                />
              </div>

              <StudioLoadingBanner
                loading={savingClone}
                title="Đang khử nhiễu tệp thu âm & huấn luyện hồ sơ giọng đọc mới..."
                subtitle="Tạo hồ sơ giọng đọc cá nhân hóa trên máy chủ cục bộ"
                steps={[
                  'Chuẩn hóa âm thanh 24kHz sạch tạp âm',
                  'Nhận diện lời mẫu & trích xuất đặc trưng giọng',
                ]}
                stepIntervalMs={2600}
              />

              <button type="submit" className="btn btn-primary" disabled={savingClone}>
                {savingClone ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
                <span>{savingClone ? 'Đang lưu hồ sơ giọng...' : 'Lưu hồ sơ giọng thu mẫu'}</span>
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
