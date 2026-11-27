import React, { useEffect, useRef, useState } from 'react';
import {
  Edit3,
  FileText,
  Film,
  Languages,
  Link2,
  Loader2,
  Mic,
  Play,
  Search,
  Subtitles,
  Upload,
  VolumeX,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import {
  FieldError,
  hasAllowedExtension,
  InlineBgmSelector,
  InlineVoiceSelector,
  isValidHttpUrl,
  MediaDropzone,
  ModeChoiceGrid,
  ParentGroupSelector,
  scrollToFirstValidationError,
  StudioLoadingBanner,
} from '../m00_core_contracts/StudioWidgets';

const MOVIE_DRAFT_KEY = 'chaos_draft_movie_v1';

function loadMovieDraft() {
  try {
    const raw = localStorage.getItem(MOVIE_DRAFT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

const AUDIO_SUB_CHOICES = [
  {
    value: 'VIET_DUB_AND_SUB',
    title: 'Lồng tiếng + Phụ đề Việt',
    subtitle: 'Đọc thuyết minh tiếng Việt truyền cảm và hiện chữ phụ đề',
    icon: Mic,
  },
  {
    value: 'VIET_SUB_KEEP_ORIG',
    title: 'Chỉ ghép Phụ đề Việt',
    subtitle: 'Giữ nguyên 100% âm thanh gốc của tập phim',
    icon: Subtitles,
  },
  {
    value: 'VIET_DUB_NO_SUB',
    title: 'Chỉ Lồng tiếng Việt',
    subtitle: 'Đọc thuyết minh, không chèn thêm chữ phụ đề dưới hình',
    icon: Languages,
  },
  {
    value: 'RAW_ORIGINAL',
    title: 'Chỉ cắt chia tập gốc',
    subtitle: 'Chia thành các phần dọc 9:16, giữ nguyên âm thanh gốc',
    icon: VolumeX,
  },
];

export default function MovieStudioForm({
  voices,
  bgmPresets,
  layoutConfig,
  projectGroups = [],
  onGroupsChanged,
  onPreviewFrameReady,
  onProjectStarted,
  notify,
}) {
  const savedDraft = loadMovieDraft();
  const rootRef = useRef(null);

  const [projectName, setProjectName] = useState(savedDraft.projectName || '');
  const [parentGroupId, setParentGroupId] = useState(savedDraft.parentGroupId || '');
  const [pathOrUrl, setPathOrUrl] = useState(savedDraft.pathOrUrl || '');
  const [sourceType, setSourceType] = useState(savedDraft.sourceType || 'VIDEO_URL');
  const [localVideoPreviewUrl, setLocalVideoPreviewUrl] = useState('');
  const [probedInfo, setProbedInfo] = useState(null);
  const [probingUrl, setProbingUrl] = useState(false);

  // Step 2
  const [outputAudioSubMode, setOutputAudioSubMode] = useState(
    savedDraft.outputAudioSubMode || 'VIET_DUB_AND_SUB'
  );
  const [voiceId, setVoiceId] = useState(
    voices.find((v) => v.profile_id === 'gemini_uslt_mytam')?.profile_id ||
      voices.find((v) => v.profile_id === 'edge_nam_minh_movie')?.profile_id ||
      voices[0]?.profile_id ||
      'gemini_uslt_mytam'
  );
  const [voiceSpeed, setVoiceSpeed] = useState(1.02);
  const [voicePitch, setVoicePitch] = useState(0.0);
  const [subtitleStyle, setSubtitleStyle] = useState(savedDraft.subtitleStyle || 'CINEMA');
  const [bgmPresetId, setBgmPresetId] = useState(null);
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.06);

  // Step 3 (Visible & Clear!)
  const [sourceLang, setSourceLang] = useState(savedDraft.sourceLang || 'auto');
  const [externalSrtPath, setExternalSrtPath] = useState('');
  const [cutStrategy, setCutStrategy] = useState(savedDraft.cutStrategy || 'SEQUENTIAL_PARTS');
  const [minSec, setMinSec] = useState(savedDraft.minSec || 65);
  const [maxSec, setMaxSec] = useState(savedDraft.maxSec || 120);
  const [duckingRatio, setDuckingRatio] = useState(savedDraft.duckingRatio || 0.18);

  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

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

  const validateCutDurationPair = (rawMin, rawMax) => {
    const a = Number(rawMin);
    const b = Number(rawMax);
    if (!Number.isFinite(a) || !Number.isFinite(b)) {
      return 'Khoảng thời lượng mỗi phần phải là số hợp lệ.';
    }
    if (a < 20 || a > 170) {
      return 'Thời lượng tối thiểu mỗi phần phải nằm trong khoảng 20 – 170 giây.';
    }
    if (b < 30 || b > 180) {
      return 'Thời lượng tối đa mỗi phần phải nằm trong khoảng 30 – 180 giây.';
    }
    if (b < a + 5) {
      return 'Thời lượng tối đa phải lớn hơn thời lượng tối thiểu ít nhất 5 giây.';
    }
    return '';
  };

  useEffect(() => {
    try {
      localStorage.setItem(
        MOVIE_DRAFT_KEY,
        JSON.stringify({
          projectName,
          parentGroupId,
          pathOrUrl: sourceType === 'VIDEO_URL' ? pathOrUrl : '',
          sourceType: 'VIDEO_URL',
          outputAudioSubMode,
          subtitleStyle,
          sourceLang,
          cutStrategy,
          minSec,
          maxSec,
          duckingRatio,
        })
      );
    } catch {
      // ignore
    }
  }, [
    projectName,
    parentGroupId,
    pathOrUrl,
    sourceType,
    outputAudioSubMode,
    subtitleStyle,
    sourceLang,
    cutStrategy,
    minSec,
    maxSec,
    duckingRatio,
  ]);

  const handleProbeUrl = async (rawVal, silentInvalid = false) => {
    const candidate = (rawVal ?? pathOrUrl).trim();
    if (!isValidHttpUrl(candidate)) {
      if (!silentInvalid) {
        const msg = 'Vui lòng dán đường dẫn video trực tuyến hợp lệ (bắt đầu bằng https://...).';
        setErrors((prev) => ({ ...prev, pathOrUrl: msg }));
        scrollToFirstValidationError(rootRef);
        notify(msg);
      }
      return;
    }
    clearError('pathOrUrl', 'videoUpload');
    setSourceType('VIDEO_URL');
    setLocalVideoPreviewUrl('');
    setProbingUrl(true);
    try {
      const info = await studioApi.probeVideoUrl(candidate);
      setProbedInfo(info);
      setPathOrUrl(info.normalized_url);
      if (!projectName.trim() && info.title) {
        setProjectName(info.title.slice(0, 90));
      }
      if (info.thumbnail_url && onPreviewFrameReady) {
        onPreviewFrameReady(info.thumbnail_url);
      }
      notify(`Đã nhận diện video: ${info.title}`);
    } catch (err) {
      setProbedInfo(null);
      notify(`Kiểm tra liên kết: ${err.message}`);
    } finally {
      setProbingUrl(false);
    }
  };

  const handleFilesSelected = async (fileList) => {
    const file = fileList?.[0];
    if (!file) return;
    if (
      !hasAllowedExtension(file.name, [
        '.mp4',
        '.mkv',
        '.mov',
        '.webm',
        '.avi',
        '.flv',
        '.ts',
        '.m4v',
      ])
    ) {
      const msg =
        'Định dạng tệp chưa hỗ trợ — vui lòng chọn tệp video (.mp4, .mkv, .mov, .webm, .avi).';
      setErrors((prev) => ({ ...prev, videoUpload: msg }));
      notify(msg);
      return;
    }
    clearError('pathOrUrl', 'videoUpload');
    setUploading(true);
    try {
      const res = await studioApi.uploadStudioFile(file, 'video');
      setSourceType('LOCAL_FILE');
      setPathOrUrl(res.local_path);
      setLocalVideoPreviewUrl(res.media_url || '');
      setProbedInfo(null);
      if (!projectName.trim()) {
        setProjectName(file.name.replace(/\.[^.]+$/, ''));
      }
      notify(`Đã tải lên video: ${file.name}`);
    } catch (err) {
      notify(`Lỗi tải video: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleSrtUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!hasAllowedExtension(file.name, ['.srt', '.vtt'])) {
      notify('Vui lòng chọn tệp phụ đề rời đúng chuẩn (.srt hoặc .vtt).');
      e.target.value = '';
      return;
    }
    try {
      const res = await studioApi.uploadStudioFile(file, 'srt');
      setExternalSrtPath(res.local_path);
      notify(`Đã đính kèm phụ đề: ${file.name}`);
    } catch (err) {
      notify(`Lỗi tải phụ đề: ${err.message}`);
    } finally {
      e.target.value = '';
    }
  };

  const submitMovie = async (autoOneClick) => {
    const cleanSource = pathOrUrl.trim();
    const nextErrs = {};

    if (!cleanSource) {
      nextErrs.pathOrUrl = 'Vui lòng dán liên kết video trực tuyến hoặc tải tệp video từ thiết bị.';
    } else if (sourceType === 'VIDEO_URL' && !isValidHttpUrl(cleanSource)) {
      nextErrs.pathOrUrl =
        'Liên kết video chưa hợp lệ (cần bắt đầu bằng https://... hoặc tải tệp video ở khung bên dưới).';
    }

    if (projectName.trim().length > 150) {
      nextErrs.projectName = 'Tiêu đề hiển thị tối đa 150 ký tự.';
    }

    const cutErr = validateCutDurationPair(minSec, maxSec);
    if (cutErr) {
      nextErrs.cutRange = cutErr;
    }

    if (Object.keys(nextErrs).length > 0) {
      setErrors(nextErrs);
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    setErrors({});
    const cleanTitle = projectName.trim() || 'Tập Phim Mới';
    const isDubbed =
      outputAudioSubMode === 'VIET_DUB_AND_SUB' || outputAudioSubMode === 'VIET_DUB_NO_SUB';
    const effSubStyle =
      outputAudioSubMode === 'VIET_DUB_NO_SUB' || outputAudioSubMode === 'RAW_ORIGINAL'
        ? 'NONE'
        : subtitleStyle === 'NONE'
        ? 'CINEMA'
        : subtitleStyle;

    setSubmitting(true);
    try {
      const started = await studioApi.startMovieProject({
        project_name: cleanTitle,
        source_type: sourceType,
        path_or_url: cleanSource,
        external_srt_path: externalSrtPath || null,
        source_language: sourceLang,
        cut_config: {
          cut_strategy: cutStrategy,
          min_clip_sec: Math.round(Number(minSec)),
          max_clip_sec: Math.round(Number(maxSec)),
          max_highlights: 5,
          drama_genre: 'Phim bộ hiện đại',
          series_title: cleanTitle,
          append_cta_outro: true,
        },
        voice_profile_id: voiceId,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        audio_config: {
          enable_narration: isDubbed,
          keep_original_audio: true,
          ducking_ratio: Number(duckingRatio),
          bgm_path: null,
          bgm_volume: Number(bgmVolume),
          subtitle_style: effSubStyle,
          subtitle_pos_y: layoutConfig.subtitle_pos_y ?? 0.84,
          subtitle_font_size: layoutConfig.subtitle_font_size ?? 52,
          voice_speed_global: Number(voiceSpeed),
          voice_pitch_global: Number(voicePitch),
        },
        layout_config: layoutConfig,
        parent_group_id: parentGroupId || null,
        auto_one_click: autoOneClick,
      });
      onProjectStarted(started.project_id, started.state);
    } catch (err) {
      notify(`Không thể bắt đầu: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!rootRef.current || rootRef.current.offsetParent === null) return;
        if (submitting || uploading) return;
        e.preventDefault();
        submitMovie(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  return (
    <div ref={rootRef} className="card">
      <div className="page-header">
        <div>
          <div className="page-title">
            <Film size={20} strokeWidth={2} /> Cắt & Dịch Video Dài Sang Khung Dọc
          </div>
          <div className="page-subtitle">
            Tự động tải video từ link hoặc máy tính, tách lời thoại bằng GPU, dịch chuẩn ngữ cảnh sang tiếng Việt và chia tập thông minh
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className="badge badge-info">Độ dài cắt: {minSec}s – {maxSec}s</span>
          <span className="badge badge-ok">
            Auto-Ducking Rạp Phim {Math.round(duckingRatio * 100)}%
          </span>
        </div>
      </div>

      {/* STEP 1 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div>
            <div className="step-title">Nguồn video đầu vào & tên bộ phim</div>
            <div className="step-desc">
              Dán liên kết (Bilibili, YouTube, TikTok...) hoặc kéo thả tệp video có sẵn từ máy tính / điện thoại
            </div>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Liên kết video trực tuyến</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
              <input
                className={`input ${errors.pathOrUrl ? 'input-error' : ''}`}
                placeholder="Dán liên kết video (https://...) vào đây..."
                value={pathOrUrl}
                onChange={(e) => {
                  const v = e.target.value;
                  setPathOrUrl(v);
                  clearError('pathOrUrl');
                  if (v.includes('http://') || v.includes('https://')) {
                    setSourceType('VIDEO_URL');
                  }
                }}
                onPaste={(e) => {
                  const pasted = e.clipboardData.getData('text');
                  if (pasted && (pasted.includes('http://') || pasted.includes('https://'))) {
                    setTimeout(() => handleProbeUrl(pasted, true), 80);
                  }
                }}
              />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={probingUrl}
              onClick={() => handleProbeUrl(pathOrUrl, false)}
            >
              {probingUrl ? <Loader2 size={15} className="spin" /> : <Search size={15} />}{' '}
              {probingUrl ? 'Đang kiểm tra...' : 'Kiểm tra link'}
            </button>
          </div>
          <FieldError message={errors.pathOrUrl} />

          <StudioLoadingBanner
            loading={probingUrl}
            title="Đang kết nối & kiểm tra siêu dữ liệu liên kết video..."
            subtitle="Hệ thống đang đọc tiêu đề, thời lượng và ảnh thu nhỏ của video gốc"
            steps={['Phân giải đường dẫn video', 'Đọc thông tin luồng phát']}
            stepIntervalMs={2200}
          />

          {probedInfo && (
            <div
              className="surface-box fade-slide-in"
              style={{
                marginTop: 9,
                borderColor: 'rgba(16, 185, 129, 0.45)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <Link2 size={16} style={{ color: 'var(--success-text)', flexShrink: 0 }} />
              <span style={{ fontSize: 13.2 }}>
                <strong>{probedInfo.title}</strong>
                {probedInfo.duration_sec > 0 &&
                  ` • Thời lượng ${Math.floor(probedInfo.duration_sec / 60)}p ${probedInfo.duration_sec % 60}s`}
              </span>
            </div>
          )}
        </div>

        <MediaDropzone
          accept="video/*"
          disabled={uploading}
          loading={uploading}
          error={errors.videoUpload}
          icon={Upload}
          title={
            uploading
              ? 'Đang tải tệp video gốc lên máy chủ...'
              : 'Hoặc kéo thả tệp video (.mp4, .mkv, .mov) trực tiếp từ máy tính / điện thoại'
          }
          hint="Tự động kiểm tra khung hình & tách luồng âm thanh stereo gốc"
          onFilesSelected={handleFilesSelected}
        />

        {localVideoPreviewUrl && (
          <div className="fade-slide-in" style={{ marginTop: 12 }}>
            <video
              controls
              src={localVideoPreviewUrl}
              style={{
                width: '100%',
                maxHeight: 220,
                borderRadius: 9,
                background: '#000',
                border: '1px solid var(--border)',
              }}
            />
          </div>
        )}

        <div className="form-group" style={{ marginTop: 13 }}>
          <label className="form-label">Tiêu đề hiển thị trên đầu các phần video</label>
          <input
            className={`input ${errors.projectName ? 'input-error' : ''}`}
            placeholder="Tự động lấy theo tên video hoặc tự nhập (VD: Tổng Tài Trở Lại)"
            value={projectName}
            onChange={(e) => {
              setProjectName(e.target.value);
              clearError('projectName');
            }}
          />
          <FieldError message={errors.projectName} />
        </div>

        <ParentGroupSelector
          projectGroups={projectGroups}
          value={parentGroupId}
          onChange={setParentGroupId}
          onGroupsChanged={onGroupsChanged}
          notify={notify}
          label="Thuộc Dự Án Cha (Gom các tập cùng Bộ phim / Series review)"
        />
      </div>

      {/* STEP 2 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">2</span>
          <div>
            <div className="step-title">Hình thức lồng tiếng, chọn giọng thuyết minh & nhạc nền</div>
            <div className="step-desc">
              Chọn 1 trong 4 kiểu xuất âm thanh; nghe thử trực tiếp chất giọng trước khi bấm chạy
            </div>
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <ModeChoiceGrid
            options={AUDIO_SUB_CHOICES}
            value={outputAudioSubMode}
            onChange={setOutputAudioSubMode}
          />
        </div>

        <div className="form-grid">
          {(outputAudioSubMode === 'VIET_DUB_AND_SUB' ||
            outputAudioSubMode === 'VIET_DUB_NO_SUB') && (
            <InlineVoiceSelector
              voices={voices}
              voiceId={voiceId}
              onChange={setVoiceId}
              voiceSpeed={voiceSpeed}
              onSpeedChange={setVoiceSpeed}
              voicePitch={voicePitch}
              onPitchChange={setVoicePitch}
              defaultCategory="MOVIE_DUB"
              label="Giọng đọc thuyết minh phim (Chuẩn Chiếu Rạp USLT / Phim Bộ)"
              sampleText="Nhưng khi chính phủ chịu lắng nghe khoa học, thì nó đã quá muộn rồi. Đại dịch đã khiến xã hội ngưng lại đột ngột."
              notify={notify}
            />
          )}

          <InlineBgmSelector
            bgmPresets={bgmPresets}
            bgmPresetId={bgmPresetId}
            onSelectPreset={setBgmPresetId}
            bgmVolume={bgmVolume}
            onVolumeChange={setBgmVolume}
            customBgmPath={customBgmPath}
            onCustomBgmChange={setCustomBgmPath}
            notify={notify}
            label="Nhạc nền lót thêm (Tùy chọn)"
          />
        </div>
      </div>

      {/* STEP 3: CLEAR VISIBLE CUTTING & SUBTITLE SETTINGS */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">3</span>
          <div>
            <div className="step-title">Cấu hình chia tập, ngôn ngữ gốc & phụ đề rời</div>
            <div className="step-desc">
              Hệ thống tự ngắt đúng dấu câu, không cắt cụt lời nhân vật giữa chừng
            </div>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Chiến lược chia đoạn video</label>
            <select
              className="select"
              value={cutStrategy}
              onChange={(e) => setCutStrategy(e.target.value)}
            >
              <option value="SEQUENTIAL_PARTS">Chia nối tiếp cả tập thành Phần 1, 2, 3...</option>
              <option value="VIRAL_HIGHLIGHTS">Chỉ lọc trích xuất các đoạn cao trào nhất</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">
              Khoảng thời lượng mỗi phần: <strong>{minSec} giây – {maxSec} giây</strong>
            </label>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="number"
                className={`input ${errors.cutRange ? 'input-error' : ''}`}
                min={20}
                max={170}
                value={minSec}
                onChange={(e) => {
                  const v = e.target.value;
                  setMinSec(v);
                  const errMsg = validateCutDurationPair(v, maxSec);
                  setErrors((prev) => {
                    const copy = { ...prev };
                    if (errMsg) copy.cutRange = errMsg;
                    else delete copy.cutRange;
                    return copy;
                  });
                }}
              />
              <span className="text-sub" style={{ fontWeight: 600 }}>
                đến
              </span>
              <input
                type="number"
                className={`input ${errors.cutRange ? 'input-error' : ''}`}
                min={30}
                max={180}
                value={maxSec}
                onChange={(e) => {
                  const v = e.target.value;
                  setMaxSec(v);
                  const errMsg = validateCutDurationPair(minSec, v);
                  setErrors((prev) => {
                    const copy = { ...prev };
                    if (errMsg) copy.cutRange = errMsg;
                    else delete copy.cutRange;
                    return copy;
                  });
                }}
              />
            </div>
            <FieldError message={errors.cutRange} />
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Ngôn ngữ gốc của phim</label>
            <select
              className="select"
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
            >
              <option value="auto">Tự động nhận diện ngôn ngữ (Khuyên dùng)</option>
              <option value="zh">Tiếng Trung</option>
              <option value="ko">Tiếng Hàn</option>
              <option value="en">Tiếng Anh</option>
              <option value="vi">Tiếng Việt (Giữ nguyên không dịch)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Kiểu chữ phụ đề tiếng Việt</label>
            <select
              className="select"
              value={subtitleStyle === 'NONE' ? 'CINEMA' : subtitleStyle}
              onChange={(e) => setSubtitleStyle(e.target.value)}
            >
              <option value="CINEMA">Phụ đề câu gọn chuẩn điện ảnh</option>
              <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ</option>
            </select>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Đính kèm phụ đề rời .SRT (nếu có sẵn sẽ bỏ qua quét âm thanh)</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="input"
                placeholder="Mặc định để trống để GPU tự nghe lời thoại"
                value={externalSrtPath}
                onChange={(e) => setExternalSrtPath(e.target.value)}
              />
              <label className="btn btn-secondary" style={{ whiteSpace: 'nowrap', cursor: 'pointer' }}>
                <FileText size={14} /> Chọn .SRT
                <input type="file" accept=".srt,.vtt" hidden onChange={handleSrtUpload} />
              </label>
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">
              Âm lượng tiếng phim gốc khi nhân vật thuyết minh nói: <strong>{Math.round(duckingRatio * 100)}%</strong>
            </label>
            <input
              type="range"
              min="0.05"
              max="0.50"
              step="0.02"
              style={{ width: '100%', marginTop: 10 }}
              value={duckingRatio}
              onChange={(e) => setDuckingRatio(parseFloat(e.target.value))}
            />
          </div>
        </div>
      </div>

      <StudioLoadingBanner
        loading={submitting}
        title="Đang khởi tạo dự án Cắt & Dịch Video Dài..."
        subtitle="Hệ thống đang lên lịch tải video gốc, nhận diện lời thoại GPU Faster-Whisper & chia tập thông minh"
        steps={[
          'Xác thực nguồn video & cấu hình chia tập',
          'Đưa vào tiến trình xử lý tự động trên GPU',
        ]}
        stepIntervalMs={1800}
      />

      {/* STICKY ACTIONS */}
      <div className="sticky-action-bar">
        <span className="text-sub" style={{ fontSize: 12.2 }}>
          Tự động lưu nháp • Bấm <strong>Ctrl + Enter</strong> để cắt &amp; thuyết minh ngay
        </span>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', flex: 1, justifyContent: 'flex-end' }}>
          <button
            className="btn btn-secondary"
            style={{ minHeight: 42 }}
            disabled={submitting || uploading || probingUrl}
            onClick={() => submitMovie(false)}
          >
            {submitting ? <Loader2 size={15} className="spin" /> : <Edit3 size={15} />}{' '}
            Xem và chỉnh lời dịch trước khi xuất
          </button>
          <button
            className="btn btn-primary"
            style={{ minWidth: 235, minHeight: 42, fontSize: 14 }}
            disabled={submitting || uploading || probingUrl}
            onClick={() => submitMovie(true)}
          >
            {submitting ? <Loader2 size={16} className="spin" /> : <Play size={16} />}{' '}
            {submitting ? 'Đang khởi tạo...' : 'Bắt đầu cắt & thuyết minh tự động'}
          </button>
        </div>
      </div>
    </div>
  );
}
