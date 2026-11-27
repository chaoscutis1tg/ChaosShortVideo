import React, { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  Edit3,
  FileText,
  Image,
  KeyRound,
  Layers,
  Play,
  RotateCcw,
  Sparkles,
  Trash2,
  Video,
  Wand2,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import {
  InlineBgmSelector,
  InlineVoiceSelector,
  ModeChoiceGrid,
  ParentGroupSelector,
} from '../m00_core_contracts/StudioWidgets';

const TOPIC_DRAFT_KEY = 'chaos_draft_topic_v1';

function loadTopicDraft() {
  try {
    const raw = localStorage.getItem(TOPIC_DRAFT_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

const VISUAL_SOURCE_CHOICES = [
  {
    value: 'AI_IMAGE',
    title: 'Ảnh minh họa chuyển động mượt',
    subtitle: 'Tự tạo hình theo từng câu kèm chuyển cảnh CapCut êm ái',
    icon: Image,
  },
  {
    value: 'HYBRID',
    title: 'Kết hợp Ảnh & Video cảnh quay',
    subtitle: 'Đan xen hình minh họa và cảnh quay thực tế sinh động',
    icon: Layers,
  },
  {
    value: 'STOCK_VIDEO',
    title: 'Ưu tiên Video cảnh quay thực',
    subtitle: 'Tìm các đoạn video dọc miễn phí từ kho Pexels / Pixabay',
    icon: Video,
  },
];

const QUICK_TOPICS = [
  {
    title: '4 cấp độ chơi đàn Guitar — Bạn đang ở đâu?',
    shortBrief:
      'Cách tự nhận biết trình độ chơi đàn hiện tại từ mới bấm hợp âm cơ bản, đệm hát mượt cho tới cảm âm solo tự do.',
  },
  {
    title: 'Tin nhắn lúc 2 giờ sáng từ tương lai',
    shortBrief:
      'Đang ngủ thì điện thoại sáng lên tin nhắn gửi từ chính số của mình dặn tuyệt đối đừng mở cửa phòng lúc 3 giờ 15.',
  },
  {
    title: 'Cách chọn cây đàn Violin đầu tiên chuẩn âm cho người mới',
    shortBrief:
      'Phân biệt gỗ thịt tự nhiên với gỗ ép, cách đo sải tay chọn kích cỡ đàn và các phụ kiện cần kiểm tra.',
  },
];

export default function TopicStudioForm({
  voices,
  bgmPresets,
  layoutConfig,
  projectGroups = [],
  onGroupsChanged,
  onProjectStarted,
  notify,
  apiKeyConfigured = false,
  onOpenApiSettings,
}) {
  const savedDraft = loadTopicDraft();
  const rootRef = useRef(null);

  const [topicTitle, setTopicTitle] = useState(savedDraft.topicTitle || '');
  const [shortBrief, setShortBrief] = useState(savedDraft.shortBrief || '');
  const [keyPoints, setKeyPoints] = useState(savedDraft.keyPoints || '');
  const [parentGroupId, setParentGroupId] = useState(savedDraft.parentGroupId || '');
  const [analyzing, setAnalyzing] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [previousTitle, setPreviousTitle] = useState('');

  const [visualMode, setVisualMode] = useState(savedDraft.visualMode || 'AI_IMAGE');
  const [voiceId, setVoiceId] = useState(
    voices.find((v) => v.profile_id === 'edge_hoai_my_fast')?.profile_id ||
      voices.find((v) => v.profile_id === 'gemini_yt_orus')?.profile_id ||
      voices[0]?.profile_id ||
      'edge_hoai_my_fast'
  );
  const [voiceSpeed, setVoiceSpeed] = useState(1.12);
  const [voicePitch, setVoicePitch] = useState(0.0);
  const [bgmPresetId, setBgmPresetId] = useState('bgm_lofi_story');
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.08);
  const [subtitleStyle, setSubtitleStyle] = useState(savedDraft.subtitleStyle || 'KARAOKE_CAPCUT');
  const [durationSec, setDurationSec] = useState(savedDraft.durationSec || 75);
  const [partCount, setPartCount] = useState(savedDraft.partCount || 1);
  const [tone, setTone] = useState(
    savedDraft.tone || 'Mở đầu cuốn hút trong 3 giây đầu, giọng kể tự nhiên sâu sắc'
  );
  const [submitting, setSubmitting] = useState(false);

  // Auto-save form draft to localStorage so F5 / reload never loses user input
  useEffect(() => {
    try {
      localStorage.setItem(
        TOPIC_DRAFT_KEY,
        JSON.stringify({
          topicTitle,
          shortBrief,
          keyPoints,
          parentGroupId,
          visualMode,
          subtitleStyle,
          durationSec,
          partCount,
          tone,
        })
      );
    } catch {
      // ignore storage quota
    }
  }, [
    topicTitle,
    shortBrief,
    keyPoints,
    parentGroupId,
    visualMode,
    subtitleStyle,
    durationSec,
    partCount,
    tone,
  ]);

  const clearDraft = () => {
    setTopicTitle('');
    setShortBrief('');
    setKeyPoints('');
    setAiAnalysis(null);
    setPreviousTitle('');
    try {
      localStorage.removeItem(TOPIC_DRAFT_KEY);
    } catch {
      // ignore
    }
    if (notify) notify('Đã làm mới nội dung nháp.');
  };

  const handleAnalyzeBrief = async () => {
    if ((topicTitle.trim() + shortBrief.trim()).length < 3) {
      notify('Vui lòng nhập tiêu đề hoặc vài từ mô tả ngắn trước khi bấm Phân tích.');
      return;
    }
    setAnalyzing(true);
    try {
      const origTitle = topicTitle.trim();
      const res = await studioApi.expandShortBrief({
        mode: 'TOPIC_VIDEO',
        raw_title: origTitle,
        short_brief: shortBrief.trim(),
        target_duration_sec: Number(durationSec),
        part_count: Number(partCount),
      });

      if (origTitle && origTitle !== res.refined_title) {
        setPreviousTitle(origTitle);
      }
      setTopicTitle(res.refined_title);
      setKeyPoints(res.expanded_description);
      if (res.recommended_tone) setTone(res.recommended_tone);
      if (res.recommended_duration_sec) setDurationSec(Number(res.recommended_duration_sec));
      if (res.recommended_part_count) setPartCount(Number(res.recommended_part_count));
      if (res.recommended_visual_mode) setVisualMode(res.recommended_visual_mode);

      if (res.recommended_voice_id && voices.some((v) => v.profile_id === res.recommended_voice_id)) {
        const matchedVoice = voices.find((v) => v.profile_id === res.recommended_voice_id);
        setVoiceId(matchedVoice.profile_id);
        if (typeof matchedVoice.speed_rate === 'number') setVoiceSpeed(matchedVoice.speed_rate);
        if (typeof matchedVoice.pitch_hz === 'number') setVoicePitch(matchedVoice.pitch_hz);
      }
      if (
        res.recommended_bgm_id &&
        bgmPresets.some((b) => b.preset_id === res.recommended_bgm_id)
      ) {
        setBgmPresetId(res.recommended_bgm_id);
      }

      setAiAnalysis(res);
      notify(
        res.used_api_key
          ? 'Đã gọi API Key phân tích & triển khai đầy đủ chủ đề, dàn ý chi tiết và cấu hình tối ưu!'
          : 'Đã mở rộng dàn ý chi tiết thành công!'
      );
    } catch (err) {
      notify(`Lỗi phân tích AI: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleStart = async (autoOneClick) => {
    const effTitle = topicTitle.trim() || shortBrief.trim().slice(0, 90);
    if (effTitle.length < 3) {
      notify('Vui lòng nhập tiêu đề hoặc mô tả ngắn video (ít nhất 3 ký tự).');
      return;
    }
    const effPoints = keyPoints.trim() || shortBrief.trim();
    setSubmitting(true);
    try {
      const res = await studioApi.startTopicProject({
        topic_title: effTitle,
        key_points: effPoints,
        visual_mode: visualMode,
        target_duration_sec: Number(durationSec),
        part_count: Number(partCount),
        narrative_tone: tone,
        voice_profile_id: voiceId,
        voice_speed_global: Number(voiceSpeed),
        voice_pitch_global: Number(voicePitch),
        subtitle_style: subtitleStyle,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        bgm_volume: bgmVolume,
        layout_config: layoutConfig,
        parent_group_id: parentGroupId || null,
        auto_one_click: autoOneClick,
      });
      onProjectStarted(res.project_id, res.state);
    } catch (err) {
      notify(`Lỗi khởi tạo: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  // Studio Shortcut: Ctrl+Enter starts automatic video generation when this tab is visible
  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        if (!rootRef.current || rootRef.current.offsetParent === null) return;
        if (submitting || analyzing) return;
        e.preventDefault();
        handleStart(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  const hasDraftText = Boolean((topicTitle + shortBrief + keyPoints).trim());

  return (
    <div ref={rootRef} className="card">
      <div className="page-header">
        <div>
          <div className="page-title">
            <FileText size={20} strokeWidth={2} /> Tạo Video Mới Từ Chủ Đề & Ý Tưởng Ngắn
          </div>
          <div className="page-subtitle">
            Viết tiêu đề kèm vài dòng mô tả ngắn → Bấm <strong>Phân tích &amp; Triển khai chi tiết (AI)</strong> để hệ thống hoàn thiện kịch bản sâu sắc nhất rồi chạy tạo video
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`badge ${apiKeyConfigured ? 'badge-ok' : 'badge-warn'}`}>
            <KeyRound size={12} /> {apiKeyConfigured ? 'API Key AI sẵn sàng' : 'Chưa gắn API Key'}
          </span>
          <span className="badge badge-info">Thời lượng: ~{durationSec}s</span>
          <span className="badge">{partCount} tập</span>
        </div>
      </div>

      {/* QUICK STARTER CHIPS */}
      <div className="summary-bar">
        <span style={{ fontSize: 12.5, fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <Sparkles size={14} style={{ color: 'var(--brand-text)' }} /> Điền nhanh ý tưởng mẫu:
        </span>
        {QUICK_TOPICS.map((qt, idx) => (
          <button
            key={idx}
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setTopicTitle(qt.title);
              setShortBrief(qt.shortBrief);
              setKeyPoints('');
              setAiAnalysis(null);
            }}
          >
            Mẫu {idx + 1}: {qt.title.slice(0, 32)}...
          </button>
        ))}
      </div>

      {/* STEP 1: SHORT BRIEF -> AI EXPAND -> READY TO RUN */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">1</span>
          <div style={{ flex: 1 }}>
            <div className="step-title">Nhập tiêu đề &amp; mô tả ngắn → Bấm Phân tích AI để triển khai chi tiết</div>
            <div className="step-desc">
              Chỉ cần gõ ý tưởng ngắn gọn — API AI sẽ tự nâng cấp tiêu đề, viết dàn ý từng phân cảnh, định hướng hình ảnh và chọn sẵn giọng đọc phù hợp nhất
            </div>
          </div>
          {!apiKeyConfigured && onOpenApiSettings && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onOpenApiSettings}>
              <KeyRound size={13} /> Nhập API Key AI
            </button>
          )}
        </div>

        <ParentGroupSelector
          projectGroups={projectGroups}
          value={parentGroupId}
          onChange={setParentGroupId}
          onGroupsChanged={onGroupsChanged}
          notify={notify}
        />

        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 5 }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Tiêu đề hoặc chủ đề của video
            </label>
            {previousTitle && previousTitle !== topicTitle && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ padding: '3px 9px', fontSize: 11.8 }}
                onClick={() => setTopicTitle(previousTitle)}
              >
                <RotateCcw size={12} /> Khôi phục tiêu đề ban đầu
              </button>
            )}
          </div>
          <input
            className="input"
            placeholder="VD: 4 cấp độ chơi đàn Guitar — Bạn đang ở đâu? (hoặc gõ vắn tắt chủ đề)"
            value={topicTitle}
            onChange={(e) => setTopicTitle(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            Mô tả ngắn / Ý tưởng sơ lược ban đầu (1 – 3 câu ngắn gọn)
          </label>
          <textarea
            className="textarea"
            style={{ minHeight: 74 }}
            placeholder="VD: Làm sao biết mình đang ở cấp độ nào khi tập Guitar, từ lúc mới bấm hợp âm bị rè cho tới lúc tự cảm âm đệm hát..."
            value={shortBrief}
            onChange={(e) => setShortBrief(e.target.value)}
          />
        </div>

        {/* PROMINENT ANALYZE & EXPAND ACTION BAR */}
        <div
          className="surface-box"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 10,
            flexWrap: 'wrap',
            borderColor: 'var(--brand)',
            marginBottom: 14,
          }}
        >
          <div style={{ minWidth: 220, flex: 1 }}>
            <div style={{ fontSize: 13.3, fontWeight: 700, color: 'var(--text-primary)' }}>
              Bước 1A: Gọi API AI phân tích &amp; viết nội dung chi tiết từ ý tưởng ngắn
            </div>
            <div className="text-sub" style={{ fontSize: 12.2, marginTop: 2 }}>
              Tự động tối ưu từ tiêu đề, câu mở đầu 3 giây, dàn ý phân cảnh cho tới bối cảnh hình ảnh để video xuất ra đạt chất lượng tốt nhất
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            style={{ minHeight: 40, padding: '8px 16px', fontWeight: 700 }}
            disabled={analyzing || submitting}
            onClick={handleAnalyzeBrief}
          >
            <Wand2 size={16} />{' '}
            {analyzing ? 'Đang gọi API phân tích chi tiết...' : 'Phân tích & Triển khai chi tiết (AI)'}
          </button>
        </div>

        {/* AI EXPANSION RESULT SUMMARY & 1-CLICK NEXT RUN */}
        {aiAnalysis && (
          <div
            className="surface-box"
            style={{
              marginBottom: 14,
              borderColor: 'rgba(16, 185, 129, 0.45)',
              background: 'rgba(16, 185, 129, 0.07)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontWeight: 700, fontSize: 13.4, color: 'var(--success-text)' }}>
                <CheckCircle2 size={16} />
                {aiAnalysis.used_api_key
                  ? 'Đã phân tích chuyên sâu qua API Key & cập nhật cấu hình tối ưu'
                  : 'Đã mở rộng dàn ý chi tiết (Gắn thêm API Key để AI viết sâu hơn)'}
              </div>
              <span className="badge badge-info">
                Đề xuất: ~{aiAnalysis.recommended_duration_sec}s • {aiAnalysis.recommended_part_count} tập
              </span>
            </div>

            {aiAnalysis.analysis_summary && (
              <div className="text-sub" style={{ fontSize: 12.8, marginBottom: 8 }}>
                {aiAnalysis.analysis_summary}
              </div>
            )}

            {aiAnalysis.hook_opening && (
              <div style={{ fontSize: 12.8, marginBottom: 8, padding: '7px 10px', borderRadius: 7, background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}>
                <strong>Câu mở đầu 3s giữ chân người xem:</strong> &ldquo;{aiAnalysis.hook_opening}&rdquo;
              </div>
            )}

            {aiAnalysis.alternative_titles?.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <div className="text-sub" style={{ fontSize: 12, fontWeight: 600, marginBottom: 5 }}>
                  Bấm để đổi nhanh sang phương án tiêu đề khác nếu thích:
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {aiAnalysis.alternative_titles.map((alt, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: 12, textAlign: 'left' }}
                      onClick={() => setTopicTitle(alt)}
                    >
                      {alt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', paddingTop: 6, borderTop: '1px solid var(--border-subtle)' }}>
              <button
                type="button"
                className="btn btn-primary"
                style={{ minHeight: 40, fontWeight: 700 }}
                disabled={submitting || analyzing}
                onClick={() => handleStart(true)}
              >
                <Play size={15} /> Tiếp theo: Chạy tạo video tự động ngay
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ minHeight: 40 }}
                disabled={submitting || analyzing}
                onClick={() => handleStart(false)}
              >
                <Edit3 size={14} /> Xem &amp; duyệt từng câu kịch bản trước khi xuất
              </button>
            </div>
          </div>
        )}

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">
            Mô tả chi tiết &amp; dàn ý từng phân cảnh (AI tự điền sau khi phân tích — bạn có thể chỉnh sửa thêm)
          </label>
          <textarea
            className="textarea"
            style={{ minHeight: 138 }}
            placeholder="- Mở đầu Hook 3s gây tò mò...&#10;- Diễn biến / Ý chính 1...&#10;- Diễn biến / Ý chính 2...&#10;- Cao trào & Thông điệp kết...&#10;(Hoặc bấm nút 'Phân tích & Triển khai chi tiết (AI)' ở trên để hệ thống tự viết đầy đủ)"
            value={keyPoints}
            onChange={(e) => setKeyPoints(e.target.value)}
          />
        </div>
      </div>

      {/* STEP 2 */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">2</span>
          <div>
            <div className="step-title">Nguồn hình ảnh minh họa, giọng đọc &amp; nhạc nền</div>
            <div className="step-desc">
              Tự động chọn sẵn giọng và nhạc hợp chủ đề sau khi phân tích — bạn vẫn có thể nghe thử hoặc đổi tùy ý
            </div>
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <ModeChoiceGrid
            options={VISUAL_SOURCE_CHOICES}
            value={visualMode}
            onChange={setVisualMode}
          />
        </div>

        <div className="form-grid">
          <InlineVoiceSelector
            voices={voices}
            voiceId={voiceId}
            onChange={setVoiceId}
            voiceSpeed={voiceSpeed}
            onSpeedChange={setVoiceSpeed}
            voicePitch={voicePitch}
            onPitchChange={setVoicePitch}
            defaultCategory="TIKTOK_SHORT"
            label="Giọng đọc dẫn chuyện (Short TikTok / YouTube Shorts / Phim)"
            sampleText={
              aiAnalysis?.hook_opening ||
              'Chỉ với ba lưu ý đơn giản dưới đây, bạn sẽ nắm bắt trọn vẹn điểm mấu chốt ngay từ lần đầu tiên.'
            }
            notify={notify}
          />
          <InlineBgmSelector
            bgmPresets={bgmPresets}
            bgmPresetId={bgmPresetId}
            onSelectPreset={setBgmPresetId}
            bgmVolume={bgmVolume}
            onVolumeChange={setBgmVolume}
            customBgmPath={customBgmPath}
            onCustomBgmChange={setCustomBgmPath}
            notify={notify}
            label="Nhạc nền kể chuyện / Acoustic"
          />
        </div>
      </div>

      {/* STEP 3: CLEAR VISIBLE DURATION, PARTS & SUBTITLES */}
      <div className="step-box">
        <div className="step-header">
          <span className="step-num">3</span>
          <div>
            <div className="step-title">Thời lượng, chia tập &amp; phong cách hiển thị phụ đề</div>
            <div className="step-desc">
              Cấu hình trực quan ngay trên màn hình để kiểm soát chính xác độ dài video xuất ra
            </div>
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">
              Thời lượng dự kiến mỗi tập: <strong>{durationSec} giây</strong>
            </label>
            <input
              type="range"
              min="30"
              max="160"
              step="5"
              style={{ width: '100%', marginTop: 8 }}
              value={durationSec}
              onChange={(e) => setDurationSec(Number(e.target.value))}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Số tập muốn chia liên tiếp</label>
            <input
              type="number"
              className="input"
              min={1}
              max={10}
              value={partCount}
              onChange={(e) => setPartCount(e.target.value)}
            />
          </div>
        </div>

        <div className="form-grid">
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Kiểu chữ phụ đề trên video</label>
            <select
              className="select"
              value={subtitleStyle}
              onChange={(e) => setSubtitleStyle(e.target.value)}
            >
              <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ</option>
              <option value="CINEMA">Phụ đề câu thanh lịch dưới màn hình</option>
              <option value="NONE">Không hiển thị chữ phụ đề</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Ghi chú giọng văn mong muốn</label>
            <input className="input" value={tone} onChange={(e) => setTone(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="sticky-action-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="text-sub" style={{ fontSize: 12.2 }}>
            Tự động lưu nháp • Bấm <strong>Ctrl + Enter</strong> để chạy ngay
          </span>
          {hasDraftText && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ padding: '4px 10px', minHeight: 30, fontSize: 11.8 }}
              onClick={clearDraft}
            >
              <Trash2 size={12} /> Làm mới form
            </button>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', flex: 1, justifyContent: 'flex-end' }}>
          <button
            className="btn btn-secondary"
            style={{ minHeight: 42 }}
            disabled={submitting || analyzing}
            onClick={() => handleStart(false)}
          >
            <Edit3 size={15} /> Xem &amp; sửa kịch bản trước
          </button>
          <button
            className="btn btn-primary"
            style={{ minWidth: 235, minHeight: 42, fontSize: 14 }}
            disabled={submitting || analyzing}
            onClick={() => handleStart(true)}
          >
            <Play size={16} /> Bắt đầu tạo video tự động
          </button>
        </div>
      </div>
    </div>
  );
}
