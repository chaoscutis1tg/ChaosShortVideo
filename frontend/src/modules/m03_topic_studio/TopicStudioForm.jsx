import React, { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  Edit3,
  FileText,
  Flame,
  Image,
  KeyRound,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
  Trash2,
  Video,
  Wand2,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import {
  FieldError,
  InlineBgmSelector,
  InlineVoiceSelector,
  ModeChoiceGrid,
  ParentGroupSelector,
  scrollToFirstValidationError,
  StudioLoadingBanner,
  SwitchCard,
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
  setLayoutConfig,
  projectGroups = [],
  onGroupsChanged,
  onProjectStarted,
  notify,
  apiKeyConfigured = false,
  onOpenApiSettings,
}) {
  const updateTopicLayout = (patch) => {
    if (setLayoutConfig) {
      setLayoutConfig((prev) => ({ ...prev, ...patch }));
    }
  };
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
  const [bgmPresetId, setBgmPresetId] = useState('lofi_vanilla_chill');
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.08);
  const [subtitleStyle, setSubtitleStyle] = useState(savedDraft.subtitleStyle || 'KARAOKE_CAPCUT');
  const [durationSec, setDurationSec] = useState(savedDraft.durationSec || 75);
  const [partCount, setPartCount] = useState(savedDraft.partCount || 1);
  const [tone, setTone] = useState(
    savedDraft.tone || 'Mở đầu cuốn hút trong 3 giây đầu, giọng kể tự nhiên sâu sắc'
  );
  const [batchMode, setBatchMode] = useState(false);
  const [batchTopicsText, setBatchTopicsText] = useState('');
  const [rotateLofiBgm, setRotateLofiBgm] = useState(true);
  const [enableSmartSfx, setEnableSmartSfx] = useState(true);
  const [smartKeywordHighlight, setSmartKeywordHighlight] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [radarOpen, setRadarOpen] = useState(false);
  const [radarItems, setRadarItems] = useState([]);
  const [loadingRadar, setLoadingRadar] = useState(false);
  const [hookScoreRes, setHookScoreRes] = useState(null);
  const [scoringHook, setScoringHook] = useState(false);

  const handleOpenTopicRadar = async (niche = 'ALL_HOT') => {
    setRadarOpen(true);
    setLoadingRadar(true);
    try {
      const items = await studioApi.fetchViralRadar(niche, 6);
      setRadarItems(items || []);
    } catch (err) {
      notify(`Lỗi quét chủ đề Viral: ${err.message}`);
    } finally {
      setLoadingRadar(false);
    }
  };

  const handleScoreTopicHook = async () => {
    const cleanT = (topicTitle.trim() || shortBrief.trim()).slice(0, 300);
    if (cleanT.length < 4) {
      notify('Vui lòng nhập tiêu đề hoặc ý tưởng ngắn trước khi chấm điểm Hook 3 giây.');
      return;
    }
    setScoringHook(true);
    try {
      const res = await studioApi.scoreOpeningHook({
        hook_text: cleanT,
        body_context: (keyPoints || shortBrief || '').slice(0, 1000),
        mode: 'TOPIC_VIDEO',
      });
      setHookScoreRes(res);
      notify(`Điểm giữ chân 3 giây đầu: ${res.overall_score}/100 — Đã tạo 3 phương án A/B!`);
    } catch (err) {
      notify(`Lỗi chấm điểm Hook: ${err.message}`);
    } finally {
      setScoringHook(false);
    }
  };

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

  // Debounced auto-save form draft (450ms) so typing never blocks the UI thread
  useEffect(() => {
    const t = setTimeout(() => {
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
    }, 450);
    return () => clearTimeout(t);
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
    const cleanTitle = topicTitle.trim();
    const cleanBrief = shortBrief.trim();
    const nextErrs = {};

    if ((cleanTitle + cleanBrief).length < 5) {
      nextErrs.topicTitle =
        'Vui lòng nhập tiêu đề hoặc ít nhất 5 ký tự mô tả ngắn trước khi bấm Phân tích AI.';
    } else if (cleanTitle.length > 180) {
      nextErrs.topicTitle = 'Tiêu đề quá dài (tối đa 180 ký tự).';
    }

    const partsNum = Number(partCount);
    if (!Number.isInteger(partsNum) || partsNum < 1 || partsNum > 10) {
      nextErrs.partCount = 'Số tập chia liên tiếp phải là số nguyên từ 1 đến 10 tập.';
    }

    if (Object.keys(nextErrs).length > 0) {
      setErrors(nextErrs);
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    setErrors({});
    setAnalyzing(true);
    try {
      const origTitle = cleanTitle;
      const res = await studioApi.expandShortBrief({
        mode: 'TOPIC_VIDEO',
        raw_title: origTitle,
        short_brief: cleanBrief,
        target_duration_sec: Math.min(160, Math.max(30, Number(durationSec) || 75)),
        part_count: partsNum,
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
    const partsNum = Number(partCount);
    const nextErrs = {};

    if (effTitle.length < 3) {
      nextErrs.topicTitle = 'Vui lòng nhập tiêu đề hoặc mô tả ngắn video (tối thiểu 3 ký tự).';
    } else if (effTitle.length > 180) {
      nextErrs.topicTitle = 'Tiêu đề video không được vượt quá 180 ký tự.';
    }
    if (!Number.isInteger(partsNum) || partsNum < 1 || partsNum > 10) {
      nextErrs.partCount = 'Số tập muốn chia phải là số nguyên từ 1 đến 10 tập.';
    }

    if (Object.keys(nextErrs).length > 0) {
      setErrors(nextErrs);
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    setErrors({});
    const effPoints = keyPoints.trim() || shortBrief.trim();
    const safeDur = Math.min(160, Math.max(30, Number(durationSec) || 75));
    setSubmitting(true);
    try {
      const res = await studioApi.startTopicProject({
        topic_title: effTitle,
        key_points: effPoints,
        visual_mode: visualMode,
        target_duration_sec: safeDur,
        part_count: partsNum,
        narrative_tone: tone.trim() || 'Giọng kể tự nhiên cuốn hút',
        voice_profile_id: voiceId,
        voice_speed_global: Number(voiceSpeed),
        voice_pitch_global: Number(voicePitch),
        subtitle_style: subtitleStyle,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        bgm_volume: bgmVolume,
        enable_smart_sfx: enableSmartSfx,
        smart_keyword_highlight: smartKeywordHighlight,
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

  const handleStartBatchTopics = async () => {
    const lines = batchTopicsText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter((s) => s.length >= 4);
    if (lines.length === 0) {
      setErrors({ batchTopics: 'Vui lòng nhập ít nhất 1 chủ đề (mỗi dòng 1 chủ đề, ít nhất 4 ký tự).' });
      scrollToFirstValidationError(rootRef);
      notify('Vui lòng nhập danh sách chủ đề cần chạy hàng loạt.');
      return;
    }
    if (lines.length > 15) {
      setErrors({ batchTopics: 'Mỗi mẻ chạy tối đa 15 chủ đề để đảm bảo tốc độ và độ ổn định GPU.' });
      notify('Tối đa 15 chủ đề mỗi mẻ chạy.');
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      const safeDur = Math.min(160, Math.max(30, Number(durationSec) || 75));
      const res = await studioApi.startTopicBatch({
        items: lines,
        visual_mode: visualMode,
        target_duration_sec: safeDur,
        part_count: Math.min(10, Math.max(1, Number(partCount) || 1)),
        narrative_tone: tone.trim() || 'Giọng kể tự nhiên cuốn hút',
        voice_profile_id: voiceId,
        voice_speed_global: Number(voiceSpeed),
        voice_pitch_global: Number(voicePitch),
        subtitle_style: subtitleStyle,
        bgm_preset_id: bgmPresetId,
        rotate_lofi_bgm: rotateLofiBgm,
        bgm_volume: bgmVolume,
        enable_smart_sfx: enableSmartSfx,
        smart_keyword_highlight: smartKeywordHighlight,
        layout_config: layoutConfig,
        parent_group_id: parentGroupId || null,
        auto_one_click: true,
      });
      setBatchTopicsText('');
      notify(`Đã xếp hàng tự động ${res.queued_count} dự án chủ đề (xoay vòng nhạc nền)!`);
      if (res.project_ids?.[0]) {
        onProjectStarted(res.project_ids[0], 'QUEUED');
      }
    } catch (err) {
      notify(`Lỗi chạy hàng loạt: ${err.message}`);
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
          {layoutConfig?.ambience_overlay && layoutConfig.ambience_overlay !== 'NONE' && (
            <span className="badge badge-ok">✨ Không khí: {layoutConfig.ambience_overlay}</span>
          )}
          {layoutConfig?.story_progress_bar_enabled && (
            <span className="badge badge-info">Thanh đốt truyện</span>
          )}
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

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
          <button
            type="button"
            className={`btn btn-sm ${!batchMode ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setBatchMode(false)}
          >
            Tạo 1 chủ đề chi tiết
          </button>
          <button
            type="button"
            className={`btn btn-sm ${batchMode ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setBatchMode(true)}
          >
            Chạy hàng loạt nhiều chủ đề (Batch Queue)
          </button>
          <button
            type="button"
            className={`btn btn-sm ${radarOpen ? 'btn-primary' : 'btn-secondary'}`}
            style={{ marginLeft: 'auto', borderColor: 'var(--brand-border)' }}
            onClick={() => (radarOpen ? setRadarOpen(false) : handleOpenTopicRadar('ALL_HOT'))}
          >
            <Flame size={13} /> {radarOpen ? 'Đóng Radar Viral' : 'Săn Chủ Đề Đang Viral'}
          </button>
        </div>

        {radarOpen && (
          <div
            className="surface-box fade-slide-in"
            style={{
              marginBottom: 12,
              borderColor: 'rgba(245, 158, 11, 0.5)',
              background: 'rgba(245, 158, 11, 0.05)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
              <strong style={{ fontSize: 12.8 }}>🔥 Chủ đề thảo luận sôi nổi dễ lên xu hướng</strong>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {[
                  ['ALL_HOT', 'Đang Hot'],
                  ['CRUSH_LOVE', 'Tình cảm'],
                  ['WORK_CAREER', 'Công sở'],
                  ['MUSIC_HOBBY', 'Nhạc cụ'],
                ].map(([nid, nlbl]) => (
                  <button
                    key={nid}
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ fontSize: 11.4, padding: '2px 8px' }}
                    disabled={loadingRadar}
                    onClick={() => handleOpenTopicRadar(nid)}
                  >
                    {nlbl}
                  </button>
                ))}
              </div>
            </div>
            {loadingRadar ? (
              <div className="text-sub" style={{ fontSize: 12 }}>
                <Loader2 size={14} className="spin" /> Đang quét chủ đề...
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
                {radarItems.map((it) => (
                  <div
                    key={it.item_id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      padding: '7px 9px',
                      borderRadius: 7,
                      background: 'var(--bg-panel)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    <div style={{ fontSize: 12.5, flex: 1 }}>
                      <span className="badge badge-info" style={{ fontSize: 10.5, marginRight: 6 }}>
                        {it.community_label}
                      </span>
                      <strong>{it.title_vi}</strong>
                    </div>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      onClick={() => {
                        setBatchMode(false);
                        setTopicTitle(it.title_vi);
                        setShortBrief(it.preview_snippet || it.title_vi);
                        setRadarOpen(false);
                        notify('Đã điền chủ đề Viral — bấm Phân tích AI để triển khai kịch bản!');
                      }}
                    >
                      Chọn chủ đề
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {batchMode ? (
          <div className="surface-box" style={{ marginBottom: 12, borderColor: 'var(--brand)' }}>
            <label className="form-label">
              Danh sách chủ đề chạy tự động lần lượt (Mỗi dòng 1 chủ đề, tối đa 15 dòng — có thể ghi <code>Tiêu đề | Ý chính</code>)
            </label>
            <textarea
              className={`textarea ${errors.batchTopics ? 'input-error' : ''}`}
              style={{ minHeight: 130 }}
              placeholder={`4 cấp độ chơi đàn Guitar | Cách nhận biết trình độ từ sơ cấp tới tự cảm âm\n3 sai lầm khiến người mới tập Violin hay mỏi vai | Cách cầm vĩ và đặt kê vai chuẩn\nTại sao nghe nhạc Lofi giúp não tập trung sâu hơn? | Cơ chế sóng âm ổn định nhịp thở`}
              value={batchTopicsText}
              onChange={(e) => {
                setBatchTopicsText(e.target.value);
                clearError('batchTopics');
              }}
            />
            <FieldError message={errors.batchTopics} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginTop: 10 }}>
              <SwitchCard checked={rotateLofiBgm} onChange={setRotateLofiBgm}>
                Tự xoay vòng đổi bài Nhạc nền Lofi CC0 cho mỗi video trong lô
              </SwitchCard>
              <button
                type="button"
                className="btn btn-primary"
                style={{ minHeight: 40, fontWeight: 700 }}
                disabled={submitting}
                onClick={handleStartBatchTopics}
              >
                {submitting ? <Loader2 size={15} className="spin" /> : <Play size={15} />}{' '}
                {submitting ? 'Đang xếp hàng...' : 'Xếp hàng chạy toàn bộ danh sách'}
              </button>
            </div>
          </div>
        ) : null}

        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 5 }}>
            <label className="form-label" style={{ marginBottom: 0 }}>
              Tiêu đề hoặc chủ đề của video
            </label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ padding: '3px 9px', fontSize: 11.8, borderColor: 'var(--brand-border)' }}
                disabled={scoringHook}
                onClick={handleScoreTopicHook}
              >
                {scoringHook ? <Loader2 size={12} className="spin" /> : <Sparkles size={12} />}{' '}
                {scoringHook ? 'Đang chấm điểm...' : '🎯 Chấm điểm Hook 3 giây & Gợi ý A/B'}
              </button>
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
          </div>
          <input
            className={`input ${errors.topicTitle ? 'input-error' : ''}`}
            placeholder="VD: 4 cấp độ chơi đàn Guitar — Bạn đang ở đâu? (hoặc gõ vắn tắt chủ đề)"
            value={topicTitle}
            onChange={(e) => {
              setTopicTitle(e.target.value);
              clearError('topicTitle');
            }}
          />
          <FieldError message={errors.topicTitle} />
          {hookScoreRes && (
            <div
              className="surface-box fade-slide-in"
              style={{
                marginTop: 8,
                padding: '9px 11px',
                borderColor: 'rgba(14, 165, 233, 0.5)',
                background: 'rgba(14, 165, 233, 0.07)',
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 12.6, marginBottom: 4 }}>
                Điểm Hook 3 Giây Đầu: <span style={{ color: '#38bdf8' }}>{hookScoreRes.overall_score}/100</span> — {hookScoreRes.verdict_label}
              </div>
              {hookScoreRes.weakness_note && (
                <div className="text-sub" style={{ fontSize: 11.8, marginBottom: 6 }}>
                  💡 {hookScoreRes.weakness_note}
                </div>
              )}
              <div style={{ display: 'grid', gap: 5 }}>
                {(hookScoreRes.variants || []).map((v, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: 8,
                      padding: '5px 8px',
                      borderRadius: 6,
                      background: 'var(--bg-panel)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    <span style={{ fontSize: 12 }}>
                      <strong style={{ color: 'var(--brand-text)' }}>[{v.style_label}]</strong> {v.hook_text}
                    </span>
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      style={{ fontSize: 11.2, whiteSpace: 'nowrap' }}
                      onClick={() => {
                        setPreviousTitle(topicTitle);
                        setTopicTitle(v.hook_text.slice(0, 175));
                        notify(`Đã đổi sang Hook "${v.style_label}"!`);
                      }}
                    >
                      Dùng câu này
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
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
            onChange={(e) => {
              setShortBrief(e.target.value);
              clearError('topicTitle');
            }}
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
            {analyzing ? <Loader2 size={16} className="spin" /> : <Wand2 size={16} />}{' '}
            {analyzing ? 'Đang gọi API phân tích chi tiết...' : 'Phân tích & Triển khai chi tiết (AI)'}
          </button>
        </div>

        <StudioLoadingBanner
          loading={analyzing}
          showSkeleton={!aiAnalysis}
          title="Đang gọi API AI phân tích chủ đề & viết dàn ý kịch bản chi tiết..."
          subtitle="Hệ thống đang tối ưu tiêu đề, câu Hook 3 giây đầu và đề xuất giọng đọc phù hợp nhất"
          steps={[
            'Phân tích ý tưởng gốc & tâm lý người xem',
            'Triển khai dàn ý từng phân cảnh & mô tả hình ảnh',
            'Chọn giọng đọc & nhạc nền tối ưu',
          ]}
          stepIntervalMs={2400}
        />

        {/* AI EXPANSION RESULT SUMMARY & 1-CLICK NEXT RUN */}
        {aiAnalysis && (
          <div
            className={`surface-box ${analyzing ? 'is-reloading-dim' : 'fade-slide-in'}`}
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
            <label className="form-label">Số tập muốn chia liên tiếp (1 – 10 tập)</label>
            <input
              type="number"
              className={`input ${errors.partCount ? 'input-error' : ''}`}
              min={1}
              max={10}
              value={partCount}
              onChange={(e) => {
                setPartCount(e.target.value);
                clearError('partCount');
              }}
              onBlur={() => {
                const n = Number(partCount);
                if (!Number.isFinite(n) || n < 1) setPartCount(1);
                else if (n > 10) setPartCount(10);
                else setPartCount(Math.round(n));
              }}
            />
            <FieldError message={errors.partCount} />
          </div>
        </div>

        <div className="form-grid" style={{ marginBottom: 12 }}>
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

        <div className="toggle-grid" style={{ marginBottom: 12 }}>
          <SwitchCard checked={enableSmartSfx} onChange={setEnableSmartSfx}>
            Âm hiệu điểm nhấn tinh tế (Micro-SFX: Chuông ấm mở đầu 3s &amp; Whoosh chuyển cảnh)
          </SwitchCard>
          <SwitchCard checked={smartKeywordHighlight} onChange={setSmartKeywordHighlight}>
            Tự tô sáng từ khóa đắt giá &amp; con số trên phụ đề
          </SwitchCard>
        </div>

        {/* SYNCED OPT-IN CINEMATIC POLISH (DEFAULT OFF) */}
        <div
          className="surface-box"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: 10,
            alignItems: 'end',
          }}
        >
          <div>
            <label className="form-label" style={{ fontSize: 12.2, marginBottom: 4 }}>
              ✨ Lớp phủ không khí điện ảnh (Tùy chọn — Mặc định Tắt)
            </label>
            <select
              className="select"
              value={layoutConfig?.ambience_overlay || 'NONE'}
              onChange={(e) => updateTopicLayout({ ambience_overlay: e.target.value })}
            >
              <option value="NONE">Tắt hiệu ứng (Giữ nguyên bản 100%)</option>
              <option value="GOLDEN_BOKEH">✨ Hạt bụi nắng vàng (Golden Bokeh)</option>
              <option value="NIGHT_RAIN">🌧️ Mưa đêm phố thị (Night Rain)</option>
              <option value="WARM_LIGHT_LEAK">🌅 Vệt nắng chiều ấm (Warm Light Leak)</option>
              <option value="VINTAGE_FILM_35MM">🎞️ Phim nhựa cổ điển 35mm</option>
            </select>
          </div>
          <SwitchCard
            checked={Boolean(layoutConfig?.story_progress_bar_enabled)}
            onChange={(val) => updateTopicLayout({ story_progress_bar_enabled: val })}
          >
            Thanh tiến trình đốt truyện trên đỉnh theo từng câu (Mặc định Tắt)
          </SwitchCard>
        </div>
      </div>

      <StudioLoadingBanner
        loading={submitting}
        title="Đang khởi tạo dự án Video Chủ Đề..."
        subtitle="Hệ thống đang chuẩn bị kịch bản chi tiết & tài nguyên hình ảnh cho từng câu dẫn"
        steps={[
          'Kiểm tra cấu hình kịch bản & giọng đọc',
          'Đưa dự án vào hàng đợi sản xuất tự động',
        ]}
        stepIntervalMs={1800}
      />

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
            {submitting ? <Loader2 size={15} className="spin" /> : <Edit3 size={15} />}{' '}
            Xem &amp; sửa kịch bản trước
          </button>
          <button
            className="btn btn-primary"
            style={{ minWidth: 235, minHeight: 42, fontSize: 14 }}
            disabled={submitting || analyzing}
            onClick={() => handleStart(true)}
          >
            {submitting ? <Loader2 size={16} className="spin" /> : <Play size={16} />}{' '}
            {submitting ? 'Đang khởi tạo...' : 'Bắt đầu tạo video tự động'}
          </button>
        </div>
      </div>
    </div>
  );
}
