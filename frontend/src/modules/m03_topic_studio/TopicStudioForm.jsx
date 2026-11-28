import React, { useEffect, useRef, useState } from 'react';
import {
  CheckCircle2,
  Edit3,
  FileText,
  Flame,
  FolderTree,
  Image,
  KeyRound,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  SlidersHorizontal,
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
  StudioCollapsible,
  StudioLoadingBanner,
  StudioPageHeader,
  StudioStepFooter,
  StudioStepNav,
  SwitchCard,
} from '../m00_core_contracts/StudioWidgets';
import MotionArtifactStudio, { MOTION_THEME_OPTIONS } from './MotionArtifactStudio';

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
    subtitle: 'Tự tạo hình theo từng câu kèm chuyển cảnh CapCut êm ái (Mặc định)',
    icon: Image,
  },
  {
    value: 'MOTION_GRAPHICS',
    title: 'Đồ họa chuyển động (Kiểu Claude / Remotion)',
    subtitle: 'Chữ động Kinetic, số liệu chạy, biểu đồ & bảng so sánh A/B kiểu Apple / Dan Koe',
    icon: Sparkles,
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
  onNavigateTab,
  showAllSteps = false,
  onToggleShowAllSteps,
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

  const [activeStep, setActiveStep] = useState(1);
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
  const [motionScenes, setMotionScenes] = useState([]);
  const [loadingMotionStoryboard, setLoadingMotionStoryboard] = useState(false);
  const [motionBrainUsed, setMotionBrainUsed] = useState('Claude / Gemini');

  const motionTheme = layoutConfig?.motion_theme || 'APPLE_GLASS_DARK';

  useEffect(() => {
    updateTopicLayout({ motion_preview_active: visualMode === 'MOTION_GRAPHICS' });
  }, [visualMode]);

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
    setMotionScenes([]);
    try {
      localStorage.removeItem(TOPIC_DRAFT_KEY);
    } catch {
      // ignore
    }
    if (notify) notify('Đã làm mới nội dung nháp.');
  };

  const handleBuildMotionStoryboard = async () => {
    const effTitle = topicTitle.trim() || shortBrief.trim().slice(0, 90);
    if (effTitle.length < 3) {
      setActiveStep(1);
      setErrors({
        topicTitle: 'Vui lòng nhập tiêu đề hoặc ý tưởng ngắn ở Bước 1 trước khi dựng phân cảnh đồ họa.',
      });
      scrollToFirstValidationError(rootRef);
      notify('Vui lòng nhập tiêu đề chủ đề ở Bước 1 trước.');
      return;
    }
    clearError('topicTitle');
    setLoadingMotionStoryboard(true);
    try {
      const res = await studioApi.previewMotionStoryboard({
        topic_title: effTitle,
        key_points: (keyPoints.trim() || shortBrief.trim()).slice(0, 5000),
        target_duration_sec: Math.min(160, Math.max(25, Number(durationSec) || 60)),
        narrative_tone: tone.trim() || 'sâu sắc, gãy gọn kiểu Claude / Dan Koe',
        motion_theme: motionTheme,
      });
      setMotionScenes(res.scenes || []);
      setMotionBrainUsed(res.used_llm_brain || 'Claude / Gemini');
      notify(
        `Đã dựng ${(res.scenes || []).length} phân cảnh Đồ họa chuyển động — mời xem thử & gõ lệnh sửa trực tiếp!`
      );
    } catch (err) {
      notify(`Lỗi dựng phân cảnh đồ họa: ${err.message}`);
    } finally {
      setLoadingMotionStoryboard(false);
    }
  };

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
      if (nextErrs.topicTitle) setActiveStep(1);
      else if (nextErrs.partCount) setActiveStep(3);
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
          ? 'Đã phân tích chuyên sâu qua API AI & tối ưu cấu hình!'
          : 'Đã mở rộng dàn ý chi tiết thành công!'
      );
    } catch (err) {
      notify(`Lỗi phân tích AI: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleStart = async (autoOneClick, customStoryboardScenes = null) => {
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
      if (nextErrs.topicTitle) setActiveStep(1);
      else if (nextErrs.partCount) setActiveStep(3);
      scrollToFirstValidationError(rootRef);
      notify(Object.values(nextErrs)[0]);
      return;
    }

    setErrors({});
    const effPoints = keyPoints.trim() || shortBrief.trim();
    const safeDur = Math.min(160, Math.max(30, Number(durationSec) || 75));
    const scenesToUse = Array.isArray(customStoryboardScenes)
      ? customStoryboardScenes
      : visualMode === 'MOTION_GRAPHICS' && motionScenes.length > 0
      ? motionScenes
      : null;
    setSubmitting(true);
    try {
      const res = await studioApi.startTopicProject({
        topic_title: effTitle,
        key_points: effPoints,
        visual_mode: visualMode,
        motion_theme: motionTheme,
        target_duration_sec: safeDur,
        part_count: scenesToUse ? 1 : partsNum,
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
        precomputed_lines: scenesToUse,
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
      setActiveStep(1);
      setErrors({
        batchTopics: 'Vui lòng nhập ít nhất 1 chủ đề (mỗi dòng 1 chủ đề, ít nhất 4 ký tự).',
      });
      scrollToFirstValidationError(rootRef);
      notify('Vui lòng nhập danh sách chủ đề cần chạy hàng loạt.');
      return;
    }
    if (lines.length > 15) {
      setActiveStep(1);
      setErrors({
        batchTopics: 'Mỗi mẻ chạy tối đa 15 chủ đề để đảm bảo tốc độ và độ ổn định GPU.',
      });
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
  const selectedVisualLabel =
    VISUAL_SOURCE_CHOICES.find((c) => c.value === visualMode)?.title || visualMode;

  const stepItems = [
    {
      title: 'Nội dung & Dàn ý AI',
      meta: topicTitle.trim() ? topicTitle.trim().slice(0, 32) : 'Nhập chủ đề hoặc chọn mẫu',
      done: Boolean((topicTitle + shortBrief).trim().length >= 3),
    },
    {
      title: 'Hình ảnh & Giọng đọc',
      meta: visualMode === 'MOTION_GRAPHICS' ? 'Motion Graphics 9:16' : selectedVisualLabel.slice(0, 26),
      done: activeStep > 2,
    },
    {
      title: 'Hoàn tất & Xuất bản',
      meta: `~${durationSec}s • ${partCount} tập`,
      done: false,
    },
  ];

  const showStep1 = showAllSteps || activeStep === 1;
  const showStep2 = showAllSteps || activeStep === 2;
  const showStep3 = showAllSteps || activeStep === 3;

  return (
    <div ref={rootRef} className="card">
      <StudioPageHeader
        icon={FileText}
        title="Tạo Video Từ Chủ Đề & Ý Tưởng"
        subtitle="Nhập ý tưởng ngắn để AI triển khai kịch bản chi tiết, chọn hình ảnh / Motion Graphics và lồng giọng đọc tự động"
        badges={[
          {
            label: apiKeyConfigured ? 'AI sẵn sàng' : 'Chưa gắn API Key',
            cls: apiKeyConfigured ? 'badge-ok' : 'badge-warn',
            icon: KeyRound,
          },
          { label: `~${durationSec}s • ${partCount} tập`, cls: 'badge-info' },
          visualMode === 'MOTION_GRAPHICS'
            ? { label: 'Motion Graphics', cls: 'badge-ok' }
            : null,
        ]}
        actions={
          !apiKeyConfigured && onOpenApiSettings ? (
            <button type="button" className="btn btn-secondary btn-sm" onClick={onOpenApiSettings}>
              <KeyRound size={13} /> Cấu hình API
            </button>
          ) : null
        }
      />

      <StudioStepNav
        steps={stepItems}
        activeStep={activeStep}
        onStepChange={setActiveStep}
        showAllSteps={showAllSteps}
        onToggleShowAll={onToggleShowAllSteps}
      />

      {/* ==================== BƯỚC 1: NỘI DUNG & DÀN Ý AI ==================== */}
      {showStep1 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">1</span>
            <div style={{ flex: 1 }}>
              <div className="step-title">Ý tưởng chủ đề &amp; Triển khai dàn ý bằng AI</div>
              <div className="step-desc">
                Chỉ cần gõ tiêu đề hoặc vài câu ngắn — AI tự tối ưu câu mở đầu 3 giây, dàn ý phân cảnh và đề xuất giọng đọc hợp nhất
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <div className="studio-segmented">
                <button
                  type="button"
                  className={`studio-seg-btn ${!batchMode ? 'active' : ''}`}
                  onClick={() => setBatchMode(false)}
                >
                  Làm 1 chủ đề
                </button>
                <button
                  type="button"
                  className={`studio-seg-btn ${batchMode ? 'active' : ''}`}
                  onClick={() => setBatchMode(true)}
                >
                  Chạy hàng loạt (Batch)
                </button>
              </div>

              <button
                type="button"
                className={`btn btn-sm ${radarOpen ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => (radarOpen ? setRadarOpen(false) : handleOpenTopicRadar('ALL_HOT'))}
              >
                <Flame size={14} /> {radarOpen ? 'Đóng xu hướng' : 'Gợi ý xu hướng'}
              </button>
            </div>
          </div>

          {/* QUICK STARTER CHIPS */}
          {!batchMode && (
            <div className="summary-bar">
              <span
                className="text-xs fw-600 text-brand"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}
              >
                <Sparkles size={14} /> Điền nhanh mẫu thử:
              </span>
              {QUICK_TOPICS.map((qt, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="filter-pill"
                  onClick={() => {
                    setTopicTitle(qt.title);
                    setShortBrief(qt.shortBrief);
                    setKeyPoints('');
                    setAiAnalysis(null);
                  }}
                >
                  Mẫu {idx + 1}: {qt.title.slice(0, 34)}...
                </button>
              ))}
            </div>
          )}

          {/* VIRAL RADAR DRAWER */}
          {radarOpen && (
            <div className="studio-callout studio-callout-brand fade-slide-in" style={{ marginBottom: 16 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                  flexWrap: 'wrap',
                  marginBottom: 10,
                }}
              >
                <strong className="text-sm">Chủ đề thảo luận đang thu hút nhiều tương tác</strong>
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
                      className="filter-pill"
                      disabled={loadingRadar}
                      onClick={() => handleOpenTopicRadar(nid)}
                    >
                      {nlbl}
                    </button>
                  ))}
                </div>
              </div>
              {loadingRadar ? (
                <div className="text-xs text-sub" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
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
                        padding: '8px 10px',
                        borderRadius: 8,
                        background: 'var(--bg-panel)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <div className="text-sm" style={{ flex: 1 }}>
                        <span className="badge badge-info" style={{ marginRight: 8 }}>
                          {it.community_label}
                        </span>
                        <span className="fw-600">{it.title_vi}</span>
                      </div>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={() => {
                          setBatchMode(false);
                          setTopicTitle(it.title_vi);
                          setShortBrief(it.preview_snippet || it.title_vi);
                          setRadarOpen(false);
                          notify('Đã điền chủ đề — bấm Phân tích AI để triển khai kịch bản!');
                        }}
                      >
                        Chọn
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {batchMode ? (
            <div className="studio-callout studio-callout-brand" style={{ marginBottom: 16 }}>
              <label className="form-label">
                Danh sách chủ đề chạy tự động lần lượt (Mỗi dòng 1 chủ đề, tối đa 15 dòng — có thể ghi{' '}
                <code>Tiêu đề | Ý chính</code>)
              </label>
              <textarea
                className={`textarea ${errors.batchTopics ? 'input-error' : ''}`}
                style={{ minHeight: 136 }}
                placeholder={`4 cấp độ chơi đàn Guitar | Cách nhận biết trình độ từ sơ cấp tới tự cảm âm\n3 sai lầm khiến người mới tập Violin hay mỏi vai | Cách cầm vĩ và đặt kê vai chuẩn\nTại sao nghe nhạc Lofi giúp não tập trung sâu hơn? | Cơ chế sóng âm ổn định nhịp thở`}
                value={batchTopicsText}
                onChange={(e) => {
                  setBatchTopicsText(e.target.value);
                  clearError('batchTopics');
                }}
              />
              <FieldError message={errors.batchTopics} />
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 10,
                  flexWrap: 'wrap',
                  marginTop: 12,
                }}
              >
                <SwitchCard checked={rotateLofiBgm} onChange={setRotateLofiBgm}>
                  Tự xoay vòng đổi bài Nhạc nền Lofi CC0 cho mỗi video trong lô
                </SwitchCard>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={submitting}
                  onClick={handleStartBatchTopics}
                >
                  {submitting ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
                  <span>{submitting ? 'Đang xếp hàng...' : 'Xếp hàng chạy toàn bộ danh sách'}</span>
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="form-group">
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
                    Tiêu đề hoặc chủ đề chính của video
                  </label>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={scoringHook}
                      onClick={handleScoreTopicHook}
                    >
                      {scoringHook ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />}
                      <span>{scoringHook ? 'Đang chấm...' : 'Chấm điểm Hook 3 giây & Gợi ý A/B'}</span>
                    </button>
                    {previousTitle && previousTitle !== topicTitle && (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => setTopicTitle(previousTitle)}
                      >
                        <RotateCcw size={13} /> Hoàn tác tiêu đề
                      </button>
                    )}
                  </div>
                </div>
                <input
                  className={`input ${errors.topicTitle ? 'input-error' : ''}`}
                  placeholder="VD: 4 cấp độ chơi đàn Guitar — Bạn đang ở đâu?"
                  value={topicTitle}
                  onChange={(e) => {
                    setTopicTitle(e.target.value);
                    clearError('topicTitle');
                  }}
                />
                <FieldError message={errors.topicTitle} />

                {hookScoreRes && (
                  <div className="studio-callout studio-callout-brand fade-slide-in" style={{ marginTop: 10 }}>
                    <div className="text-sm fw-700" style={{ marginBottom: 4 }}>
                      Điểm Hook 3 Giây Đầu:{' '}
                      <span className="text-brand">{hookScoreRes.overall_score}/100</span> —{' '}
                      {hookScoreRes.verdict_label}
                    </div>
                    {hookScoreRes.weakness_note && (
                      <div className="text-xs text-sub" style={{ marginBottom: 8 }}>
                        Gợi ý cải thiện: {hookScoreRes.weakness_note}
                      </div>
                    )}
                    <div style={{ display: 'grid', gap: 6 }}>
                      {(hookScoreRes.variants || []).map((v, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: 8,
                            padding: '7px 10px',
                            borderRadius: 8,
                            background: 'var(--bg-panel)',
                            border: '1px solid var(--border)',
                          }}
                        >
                          <span className="text-xs">
                            <strong className="text-brand">[{v.style_label}]</strong> {v.hook_text}
                          </span>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            style={{ whiteSpace: 'nowrap' }}
                            onClick={() => {
                              setPreviousTitle(topicTitle);
                              setTopicTitle(v.hook_text.slice(0, 175));
                              notify(`Đã đổi sang Hook "${v.style_label}"!`);
                            }}
                          >
                            Áp dụng
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="form-group">
                <label className="form-label">Mô tả ngắn / Ý tưởng sơ lược (1 – 3 câu)</label>
                <textarea
                  className="textarea"
                  style={{ minHeight: 78 }}
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
                className="studio-callout studio-callout-brand"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 12,
                  flexWrap: 'wrap',
                  marginBottom: 16,
                }}
              >
                <div style={{ minWidth: 220, flex: 1 }}>
                  <div className="text-sm fw-700 text-main">
                    Gọi AI phân tích &amp; viết dàn ý kịch bản chi tiết từ ý tưởng ngắn
                  </div>
                  <div className="text-xs text-sub" style={{ marginTop: 2 }}>
                    Tự động nâng cấp tiêu đề, câu mở đầu 3 giây, dàn ý phân cảnh và chọn sẵn giọng đọc tối ưu
                  </div>
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={analyzing || submitting}
                  onClick={handleAnalyzeBrief}
                >
                  {analyzing ? <Loader2 size={16} className="spin" /> : <Wand2 size={16} />}
                  <span>{analyzing ? 'Đang phân tích...' : 'Phân tích & Viết dàn ý (AI)'}</span>
                </button>
              </div>

              <StudioLoadingBanner
                loading={analyzing}
                showSkeleton={!aiAnalysis}
                title="Đang phân tích chủ đề & viết dàn ý kịch bản chi tiết..."
                subtitle="Hệ thống đang tối ưu tiêu đề, câu Hook 3 giây đầu và đề xuất giọng đọc phù hợp nhất"
                steps={[
                  'Phân tích ý tưởng gốc & tâm lý người xem',
                  'Triển khai dàn ý từng phân cảnh & mô tả hình ảnh',
                  'Chọn giọng đọc & nhạc nền tối ưu',
                ]}
                stepIntervalMs={2400}
              />

              {aiAnalysis && (
                <div
                  className={`studio-callout studio-callout-success ${
                    analyzing ? 'is-reloading-dim' : 'fade-slide-in'
                  }`}
                  style={{ marginBottom: 16 }}
                >
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
                    <div
                      className="text-sm fw-700 text-success"
                      style={{ display: 'flex', alignItems: 'center', gap: 7 }}
                    >
                      <CheckCircle2 size={16} />
                      <span>
                        {aiAnalysis.used_api_key
                          ? 'Đã phân tích chuyên sâu qua AI & cập nhật cấu hình tối ưu'
                          : 'Đã mở rộng dàn ý chi tiết'}
                      </span>
                    </div>
                    <span className="badge badge-info">
                      Đề xuất: ~{aiAnalysis.recommended_duration_sec}s • {aiAnalysis.recommended_part_count} tập
                    </span>
                  </div>

                  {aiAnalysis.analysis_summary && (
                    <div className="text-sm text-sub" style={{ marginBottom: 8 }}>
                      {aiAnalysis.analysis_summary}
                    </div>
                  )}

                  {aiAnalysis.hook_opening && (
                    <div
                      className="surface-box text-sm"
                      style={{ marginBottom: 10 }}
                    >
                      <strong>Câu mở đầu 3s giữ chân người xem:</strong> &ldquo;{aiAnalysis.hook_opening}&rdquo;
                    </div>
                  )}

                  {aiAnalysis.alternative_titles?.length > 0 && (
                    <div>
                      <div className="text-xs fw-600 text-sub" style={{ marginBottom: 6 }}>
                        Đổi nhanh phương án tiêu đề khác:
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {aiAnalysis.alternative_titles.map((alt, idx) => (
                          <button
                            key={idx}
                            type="button"
                            className="filter-pill"
                            onClick={() => setTopicTitle(alt)}
                          >
                            {alt}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
                  Dàn ý chi tiết từng phân cảnh (AI tự điền hoặc bạn tự biên tập)
                </label>
                <textarea
                  className="textarea"
                  style={{ minHeight: 132 }}
                  placeholder={`- Mở đầu Hook 3s gây tò mò...\n- Diễn biến / Ý chính 1...\n- Diễn biến / Ý chính 2...\n- Cao trào & Thông điệp kết...`}
                  value={keyPoints}
                  onChange={(e) => setKeyPoints(e.target.value)}
                />
              </div>
            </>
          )}

          <StudioCollapsible
            icon={FolderTree}
            title="Quản lý theo Nhóm Dự Án Cha (Series / Chiến dịch)"
            subtitle="Tùy chọn gom các tập video cùng chủ đề vào một thư mục Series"
            badge={parentGroupId ? 'Đã chọn nhóm' : ''}
          >
            <ParentGroupSelector
              projectGroups={projectGroups}
              value={parentGroupId}
              onChange={setParentGroupId}
              onGroupsChanged={onGroupsChanged}
              notify={notify}
            />
          </StudioCollapsible>
        </div>
      )}

      {/* ==================== BƯỚC 2: HÌNH ẢNH & GIỌNG ĐỌC ==================== */}
      {showStep2 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">2</span>
            <div>
              <div className="step-title">Phong cách hình ảnh, Giọng đọc &amp; Nhạc nền</div>
              <div className="step-desc">
                Chọn kiểu hình ảnh minh họa hoặc Đồ họa chuyển động kiểu Claude / Remotion, kết hợp nghe thử giọng đọc trực tiếp
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <ModeChoiceGrid
              options={VISUAL_SOURCE_CHOICES}
              value={visualMode}
              onChange={(nextMode) => {
                setVisualMode(nextMode);
                if (nextMode === 'MOTION_GRAPHICS' && subtitleStyle === 'KARAOKE_CAPCUT') {
                  setSubtitleStyle('CINEMA');
                }
              }}
            />
          </div>

          {visualMode === 'MOTION_GRAPHICS' && (
            <div
              className="studio-callout studio-callout-brand fade-slide-in"
              style={{
                marginBottom: 16,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                flexWrap: 'wrap',
              }}
            >
              <div style={{ flex: 1, minWidth: 240 }}>
                <div className="text-sm fw-700" style={{ marginBottom: 4 }}>
                  Bàn dựng Đồ Họa Chuyển Động (Motion Graphics kiểu Claude / Remotion)
                </div>
                <div className="text-xs text-sub">
                  AI tự dựng hoạt ảnh chữ Kinetic, bộ đếm số, biểu đồ cột &amp; bảng đối chiếu A/B khớp từng câu đọc — xem trước 60fps &amp; gõ lệnh sửa trực tiếp
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <select
                  className="select"
                  style={{ width: 'auto', minWidth: 235 }}
                  value={motionTheme}
                  onChange={(e) => updateTopicLayout({ motion_theme: e.target.value })}
                >
                  {MOTION_THEME_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={loadingMotionStoryboard || submitting}
                  onClick={handleBuildMotionStoryboard}
                >
                  {loadingMotionStoryboard ? (
                    <Loader2 size={15} className="spin" />
                  ) : (
                    <Sparkles size={15} />
                  )}
                  <span>
                    {loadingMotionStoryboard
                      ? 'Đang dựng phân cảnh...'
                      : motionScenes.length > 0
                      ? 'Tạo lại Storyboard'
                      : 'Dựng Storyboard Tương Tác'}
                  </span>
                </button>
              </div>
            </div>
          )}

          {visualMode === 'MOTION_GRAPHICS' && motionScenes.length > 0 && (
            <MotionArtifactStudio
              scenes={motionScenes}
              setScenes={setMotionScenes}
              motionTheme={motionTheme}
              onChangeTheme={(nextT) => updateTopicLayout({ motion_theme: nextT })}
              usedBrainLabel={motionBrainUsed}
              submitting={submitting}
              onRenderMp4={(editedScenes) => handleStart(true, editedScenes)}
              notify={notify}
            />
          )}

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
              onOpenVoiceLab={onNavigateTab ? () => onNavigateTab('voices') : null}
              label="Giọng đọc dẫn chuyện"
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
      )}

      {/* ==================== BƯỚC 3: HOÀN TẤT & XUẤT BẢN ==================== */}
      {showStep3 && (
        <div className="step-box fade-slide-in">
          <div className="step-header">
            <span className="step-num">3</span>
            <div>
              <div className="step-title">Thời lượng, Chia tập &amp; Phụ đề</div>
              <div className="step-desc">
                Kiểm tra thông số độ dài video và phụ đề trước khi đưa vào tiến trình kết xuất tự động
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

          <div className="form-grid" style={{ marginBottom: 16 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Kiểu chữ phụ đề trên video</label>
              <select
                className="select"
                value={subtitleStyle}
                onChange={(e) => setSubtitleStyle(e.target.value)}
              >
                <option value="KARAOKE_CAPCUT">Chữ chạy nổi bật từng từ (Karaoke CapCut)</option>
                <option value="CINEMA">Phụ đề câu thanh lịch dưới màn hình</option>
                <option value="NONE">Không hiển thị chữ phụ đề</option>
              </select>
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Ghi chú giọng văn mong muốn</label>
              <input className="input" value={tone} onChange={(e) => setTone(e.target.value)} />
            </div>
          </div>

          <div className="toggle-grid">
            <SwitchCard checked={enableSmartSfx} onChange={setEnableSmartSfx}>
              Âm hiệu điểm nhấn tinh tế (Chuông mở đầu 3s &amp; Whoosh chuyển cảnh)
            </SwitchCard>
            <SwitchCard checked={smartKeywordHighlight} onChange={setSmartKeywordHighlight}>
              Tự tô sáng từ khóa đắt giá &amp; con số trên phụ đề
            </SwitchCard>
          </div>

          <StudioCollapsible
            icon={SlidersHorizontal}
            title="Hiệu ứng không khí điện ảnh & Thanh đốt truyện (Tùy chọn)"
            subtitle="Mặc định tắt để giữ khung hình sạch — bật khi cần hiệu ứng Bokeh / Mưa đêm / Phim 35mm"
            badge={
              (layoutConfig?.ambience_overlay && layoutConfig.ambience_overlay !== 'NONE') ||
              layoutConfig?.story_progress_bar_enabled
                ? 'Đang bật'
                : ''
            }
          >
            <div className="form-grid" style={{ alignItems: 'end' }}>
              <div>
                <label className="form-label">Lớp phủ không khí điện ảnh</label>
                <select
                  className="select"
                  value={layoutConfig?.ambience_overlay || 'NONE'}
                  onChange={(e) => updateTopicLayout({ ambience_overlay: e.target.value })}
                >
                  <option value="NONE">Tắt hiệu ứng (Giữ nguyên bản 100%)</option>
                  <option value="GOLDEN_BOKEH">Hạt bụi nắng vàng (Golden Bokeh)</option>
                  <option value="NIGHT_RAIN">Mưa đêm phố thị (Night Rain)</option>
                  <option value="WARM_LIGHT_LEAK">Vệt nắng chiều ấm (Warm Light Leak)</option>
                  <option value="VINTAGE_FILM_35MM">Phim nhựa cổ điển 35mm</option>
                </select>
              </div>
              <SwitchCard
                checked={Boolean(layoutConfig?.story_progress_bar_enabled)}
                onChange={(val) => updateTopicLayout({ story_progress_bar_enabled: val })}
              >
                Thanh tiến trình đốt truyện trên đỉnh theo từng câu
              </SwitchCard>
            </div>
          </StudioCollapsible>
        </div>
      )}

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

      <StudioStepFooter
        activeStep={activeStep}
        totalSteps={3}
        showAllSteps={showAllSteps}
        onStepChange={setActiveStep}
        nextStepLabel={
          activeStep === 1 ? 'Tiếp tục: Chọn Hình & Giọng' : 'Tiếp tục: Hoàn tất & Xuất'
        }
        hintText="Tự động lưu nháp • Bấm Ctrl + Enter để chạy ngay"
        extraLeft={
          hasDraftText ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearDraft}>
              <Trash2 size={13} /> Làm mới
            </button>
          ) : null
        }
        secondaryAction={{
          label: 'Duyệt kịch bản trước',
          icon: submitting ? <Loader2 size={15} className="spin" /> : <Edit3 size={15} />,
          disabled: submitting || analyzing,
          onClick: () => handleStart(false),
        }}
        primaryAction={{
          label: submitting ? 'Đang khởi tạo...' : 'Bắt đầu tạo video tự động',
          icon: submitting ? <Loader2 size={16} className="spin" /> : <Play size={16} />,
          disabled: submitting || analyzing,
          onClick: () => handleStart(true),
        }}
      />
    </div>
  );
}
