import React, { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  Archive,
  ArrowLeft,
  ArrowRight,
  Clock,
  Copy,
  Download,
  Edit3,
  FileText,
  Film,
  FolderKanban,
  FolderOpen,
  Languages,
  Loader2,
  Pause,
  Play,
  RefreshCw,
  ShoppingBag,
  Square,
  Trash2,
  Volume2,
  X,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import {
  copyTextSafe,
  DEFAULT_LAYOUT_CONFIG,
  formatSecondsVi,
  STAGE_LABELS,
} from '../m00_core_contracts/constants';
import { InlineBgmSelector, InlineVoiceSelector } from '../m00_core_contracts/StudioWidgets';

const RUNNING_STATES = [
  'QUEUED',
  'INGESTING',
  'TRANSCRIBING_GPU',
  'AI_ANALYZING',
  'GENERATING_ASSETS',
  'RENDERING_NVENC',
  'PACKAGING_SEO',
];

function ModeIcon({ mode }) {
  if (mode === 'MOVIE_CLIPPER') return <Film size={15} strokeWidth={1.8} />;
  if (mode === 'PRODUCT_SHOWCASE') return <ShoppingBag size={15} strokeWidth={1.8} />;
  return <FileText size={15} strokeWidth={1.8} />;
}

export default function ProjectWorkspaceView({
  activeProjectId,
  projects,
  onSelectProject,
  onProjectsRefresh,
  voices,
  bgmPresets,
  layoutConfig,
  setLayoutConfig,
  onPreviewFrameReady,
  notify,
}) {
  const [filterMode, setFilterMode] = useState('ALL');
  const [detail, setDetail] = useState(null);
  const [liveProgress, setLiveProgress] = useState(null);
  const [quickEditOpen, setQuickEditOpen] = useState(false);
  const [editableClips, setEditableClips] = useState([]);
  const [editablePhotoList, setEditablePhotoList] = useState([]);
  const [selectedParts, setSelectedParts] = useState([]);
  const [reviewAudioSubMode, setReviewAudioSubMode] = useState('VIET_DUB_AND_SUB');
  const [selectedVoice, setSelectedVoice] = useState(
    voices[0]?.profile_id || 'edge_nam_nghe_nhan'
  );
  const [globalVoiceSpeed, setGlobalVoiceSpeed] = useState(1.02);
  const [globalVoicePitch, setGlobalVoicePitch] = useState(-1.2);
  const [previewingLineKey, setPreviewingLineKey] = useState('');
  const lineAudioRef = useRef(null);

  const [bgmPresetId, setBgmPresetId] = useState(null);
  const [customBgmPath, setCustomBgmPath] = useState(null);
  const [bgmVolume, setBgmVolume] = useState(0.06);
  const [translating, setTranslating] = useState(false);
  const [busyAction, setBusyAction] = useState(false);

  const syncEditableFromDetail = (d, alsoRestoreLayout = false) => {
    if (!d?.clips) return;
    setEditableClips(
      d.clips.map((c) => ({
        clip_id: c.clip_id,
        part_number: c.part_number,
        source_start_ms: c.start_ms,
        source_end_ms: c.end_ms,
        hook_banner_title: c.hook_banner_title,
        append_cta_outro: Boolean(c.append_cta_outro),
        lines: (c.lines || []).map((ln) => ({
          seq_index: ln.seq_index,
          rel_start_ms: ln.rel_start_ms,
          rel_end_ms: ln.rel_end_ms,
          original_text: ln.original_text || '',
          vi_text: ln.vi_narration_text || '',
          image_prompt: ln.image_prompt || '',
          stock_keywords: [],
          matched_image_index:
            ln.matched_image_index !== undefined ? ln.matched_image_index : null,
          is_real_demo_slot: Boolean(ln.is_real_demo_slot),
          callout_label: ln.callout_label || '',
          voice_speed_override:
            ln.voice_speed_override !== undefined && ln.voice_speed_override !== null
              ? Number(ln.voice_speed_override)
              : null,
          voice_pitch_override:
            ln.voice_pitch_override !== undefined && ln.voice_pitch_override !== null
              ? Number(ln.voice_pitch_override)
              : null,
        })),
      }))
    );
    setSelectedParts((prev) =>
      prev.length > 0 ? prev : d.clips.map((c) => c.part_number)
    );

    if (d.product_image_paths?.length > 0 && d.product_image_urls?.length > 0) {
      setEditablePhotoList(
        d.product_image_paths.map((p, idx) => ({
          local_path: p,
          media_url: d.product_image_urls[idx] || '',
          isVideo: /\.(mp4|mov|mkv|webm|avi)$/i.test(p),
        }))
      );
    } else {
      setEditablePhotoList([]);
    }

    const savedReq = d.saved_request || {};
    const matchedVoiceProf = voices.find(
      (v) => v.profile_id === (savedReq.voice_profile_id || selectedVoice)
    );
    if (savedReq.voice_profile_id) {
      setSelectedVoice(savedReq.voice_profile_id);
    }
    if (savedReq.voice_speed_global !== undefined && savedReq.voice_speed_global !== null) {
      setGlobalVoiceSpeed(Number(savedReq.voice_speed_global));
    } else if (matchedVoiceProf) {
      setGlobalVoiceSpeed(Number(matchedVoiceProf.speed_rate));
    }
    if (savedReq.voice_pitch_global !== undefined && savedReq.voice_pitch_global !== null) {
      setGlobalVoicePitch(Number(savedReq.voice_pitch_global));
    } else if (matchedVoiceProf) {
      setGlobalVoicePitch(Number(matchedVoiceProf.pitch_hz));
    }
    if (savedReq.bgm_preset_id !== undefined) {
      setBgmPresetId(savedReq.bgm_preset_id);
    }
    if (savedReq.custom_bgm_path !== undefined) {
      setCustomBgmPath(savedReq.custom_bgm_path);
    }
    if (savedReq.bgm_volume !== undefined) {
      setBgmVolume(Number(savedReq.bgm_volume));
    }
    if (alsoRestoreLayout && savedReq.layout_config && setLayoutConfig) {
      setLayoutConfig({ ...DEFAULT_LAYOUT_CONFIG, ...savedReq.layout_config });
    }
  };

  const loadDetail = async (pid, forceRebuildEditor = false) => {
    if (!pid) return;
    try {
      const d = await studioApi.getProjectDetail(pid);
      setDetail((prev) => {
        if (prev && prev.state !== d.state && onProjectsRefresh) {
          onProjectsRefresh();
        }
        if (
          d.state === 'AWAITING_REVIEW' &&
          (forceRebuildEditor || !prev || prev.id !== d.id || prev.state !== 'AWAITING_REVIEW')
        ) {
          syncEditableFromDetail(d, true);
          setQuickEditOpen(true);
        }
        return d;
      });
      setLiveProgress(d.live_progress || null);
      if (d.source_media?.preview_urls?.[0]) {
        onPreviewFrameReady(d.source_media.preview_urls[0]);
      } else if (d.product_image_urls?.[0]) {
        onPreviewFrameReady(d.product_image_urls[0]);
      }
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    setSelectedParts([]);
    setQuickEditOpen(false);
    if (!activeProjectId) return;
    loadDetail(activeProjectId, true);

    const ws = studioApi.connectProgressSocket(activeProjectId, (ev) => {
      setLiveProgress(ev);
      if (['AWAITING_REVIEW', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED'].includes(ev.stage)) {
        loadDetail(activeProjectId, ev.stage === 'AWAITING_REVIEW');
      }
    });

    const timer = setInterval(() => loadDetail(activeProjectId, false), 2200);
    return () => {
      clearInterval(timer);
      ws.close();
    };
  }, [activeProjectId]);

  const handleOpenQuickReEdit = () => {
    if (!detail) return;
    syncEditableFromDetail(detail, true);
    setQuickEditOpen((prev) => !prev);
  };

  const handlePreviewSingleLine = async (cIdx, lIdx, lineObj) => {
    const key = `${cIdx}_${lIdx}`;
    if (previewingLineKey === key && lineAudioRef.current) {
      lineAudioRef.current.pause();
      setPreviewingLineKey('');
      return;
    }
    setPreviewingLineKey(key);
    try {
      const spd = lineObj.voice_speed_override ?? globalVoiceSpeed;
      const ptc = lineObj.voice_pitch_override ?? globalVoicePitch;
      const res = await studioApi.previewVoice(selectedVoice, lineObj.vi_text, spd, ptc);
      if (lineAudioRef.current) lineAudioRef.current.pause();
      const player = new Audio(`${res.audio_url}?t=${Date.now()}`);
      lineAudioRef.current = player;
      player.onended = () => setPreviewingLineKey('');
      player.onerror = () => setPreviewingLineKey('');
      await player.play();
    } catch (err) {
      setPreviewingLineKey('');
      notify(`Lỗi nghe thử câu: ${err.message}`);
    }
  };

  const handlePause = async () => {
    if (!detail) return;
    setBusyAction(true);
    try {
      const updated = await studioApi.pauseProject(detail.id);
      setDetail(updated);
      setLiveProgress(updated.live_progress || null);
      if (onProjectsRefresh) onProjectsRefresh();
      notify('Đã tạm dừng dự án.');
    } catch (err) {
      notify(`Lỗi tạm dừng: ${err.message}`);
    } finally {
      setBusyAction(false);
    }
  };

  const handleResume = async () => {
    if (!detail) return;
    setBusyAction(true);
    try {
      const updated = await studioApi.resumeProject(detail.id);
      setDetail(updated);
      setLiveProgress(updated.live_progress || null);
      if (onProjectsRefresh) onProjectsRefresh();
      notify('Đã tiếp tục chạy dự án.');
    } catch (err) {
      notify(`Lỗi tiếp tục: ${err.message}`);
    } finally {
      setBusyAction(false);
    }
  };

  const handleCancel = async () => {
    if (!detail) return;
    setBusyAction(true);
    try {
      const updated = await studioApi.cancelProject(detail.id);
      setDetail(updated);
      setLiveProgress(updated.live_progress || null);
      if (onProjectsRefresh) onProjectsRefresh();
      notify('Đã dừng dự án (các phần hoàn tất trước đó vẫn được giữ lại).');
    } catch (err) {
      notify(`Lỗi dừng dự án: ${err.message}`);
    } finally {
      setBusyAction(false);
    }
  };

  const handleDeleteProject = async (pid) => {
    setBusyAction(true);
    try {
      await studioApi.deleteProject(pid);
      notify('Đã xóa dự án khỏi danh sách (tệp video MP4 đã xuất vẫn được giữ nguyên).');
      if (onProjectsRefresh) await onProjectsRefresh();
      setDetail(null);
    } catch (err) {
      notify(`Lỗi xóa dự án: ${err.message}`);
    } finally {
      setBusyAction(false);
    }
  };

  const handleTranslateAllToVi = async () => {
    if (!detail) return;
    setTranslating(true);
    try {
      const updated = await studioApi.translateProjectToVi(detail.id);
      setDetail(updated);
      syncEditableFromDetail(updated, false);
      notify('Đã dịch toàn bộ lời thoại sang tiếng Việt.');
    } catch (err) {
      notify(`Lỗi dịch tự động: ${err.message}`);
    } finally {
      setTranslating(false);
    }
  };

  const handleLinePatch = (clipIdx, lineIdx, patchObj) => {
    setEditableClips((prev) =>
      prev.map((c, ci) =>
        ci !== clipIdx
          ? c
          : {
              ...c,
              lines: c.lines.map((l, li) => (li !== lineIdx ? l : { ...l, ...patchObj })),
            }
      )
    );
  };

  const moveEditablePhoto = (fromIdx, toIdx) => {
    setEditablePhotoList((prev) => {
      if (toIdx < 0 || toIdx >= prev.length || fromIdx === toIdx) return prev;
      const copy = [...prev];
      const [item] = copy.splice(fromIdx, 1);
      copy.splice(toIdx, 0, item);
      const firstImg = copy.find((x) => !x.isVideo);
      if (firstImg?.media_url && onPreviewFrameReady) {
        onPreviewFrameReady(firstImg.media_url);
      }
      return copy;
    });
  };

  const handleBannerEdit = (clipIdx, newBanner) => {
    setEditableClips((prev) =>
      prev.map((c, ci) => (ci !== clipIdx ? c : { ...c, hook_banner_title: newBanner }))
    );
  };

  const togglePart = (partNum) => {
    setSelectedParts((prev) =>
      prev.includes(partNum) ? prev.filter((p) => p !== partNum) : [...prev, partNum]
    );
  };

  const updateQuickLayout = (patch) => {
    if (setLayoutConfig) {
      setLayoutConfig((prev) => ({ ...prev, ...patch }));
    }
  };

  const handleApproveAndRender = async () => {
    if (!detail) return;
    if (selectedParts.length === 0) {
      notify('Vui lòng chọn ít nhất 1 phần để xuất video.');
      return;
    }

    const isMovie = detail.mode === 'MOVIE_CLIPPER';
    const isDubbed =
      reviewAudioSubMode === 'VIET_DUB_AND_SUB' || reviewAudioSubMode === 'VIET_DUB_NO_SUB';
    const effSubStyle =
      reviewAudioSubMode === 'VIET_DUB_NO_SUB' || reviewAudioSubMode === 'RAW_ORIGINAL'
        ? 'NONE'
        : isMovie || detail.mode === 'PRODUCT_SHOWCASE'
        ? 'CINEMA'
        : 'KARAOKE_CAPCUT';

    setBusyAction(true);
    try {
      await studioApi.renderApprovedProject(detail.id, {
        voice_profile_id: selectedVoice,
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        audio_config: {
          enable_narration: isDubbed,
          keep_original_audio: isMovie,
          ducking_ratio: 0.18,
          bgm_path: null,
          bgm_volume: bgmVolume,
          subtitle_style: effSubStyle,
          subtitle_pos_y: layoutConfig.subtitle_pos_y ?? 0.84,
          subtitle_font_size: layoutConfig.subtitle_font_size ?? 52,
          voice_speed_global: Number(globalVoiceSpeed),
          voice_pitch_global: Number(globalVoicePitch),
        },
        layout_config: layoutConfig,
        clips: editableClips,
        selected_part_numbers: selectedParts,
        image_paths_override:
          editablePhotoList.length > 0 ? editablePhotoList.map((p) => p.local_path) : null,
      });
      setQuickEditOpen(false);
      notify(`Đã bắt đầu xuất ${selectedParts.length} phần video với cấu hình mới.`);
      loadDetail(detail.id);
      if (onProjectsRefresh) onProjectsRefresh();
    } catch (err) {
      notify(`Lỗi xuất video: ${err.message}`);
    } finally {
      setBusyAction(false);
    }
  };

  const copyText = (txt, label) => {
    copyTextSafe(txt).then(() => notify(`Đã sao chép ${label}.`));
  };

  const filteredProjects = projects.filter((p) => {
    if (filterMode === 'RUNNING')
      return RUNNING_STATES.includes(p.state) || p.state === 'PAUSED';
    if (filterMode === 'REVIEW') return p.state === 'AWAITING_REVIEW';
    if (filterMode === 'DONE') return p.state === 'COMPLETED';
    return true;
  });

  const isRunning = detail && RUNNING_STATES.includes(detail.state) && detail.is_active_in_memory;
  const isPaused = detail && detail.state === 'PAUSED';
  const isInterruptedFromOldSession =
    detail && RUNNING_STATES.includes(detail.state) && !detail.is_active_in_memory;
  const canResume =
    detail &&
    (isPaused ||
      isInterruptedFromOldSession ||
      detail.state === 'CANCELLED' ||
      detail.state === 'FAILED');
  const canQuickEdit =
    detail &&
    detail.clips?.length > 0 &&
    ['COMPLETED', 'AWAITING_REVIEW', 'FAILED', 'CANCELLED'].includes(detail.state);
  const completedClips = (detail?.clips || []).filter((c) => Boolean(c.output_mp4_path));
  const pctVal = Math.min(100, Math.max(0, liveProgress?.percent || 0));
  const savedAspect = detail?.saved_request?.layout_config?.aspect_ratio || '9:16';
  const videoCssAspect =
    savedAspect === '1:1' ? '1 / 1' : savedAspect === '4:5' ? '4 / 5' : '9 / 16';

  return (
    <div>
      {/* PROJECT LIST */}
      <div className="card">
        <div className="page-header" style={{ marginBottom: 12 }}>
          <div className="page-title">
            <FolderKanban size={19} strokeWidth={1.9} /> Danh Sách Dự Án & Hàng Đợi
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[
              ['ALL', `Tất cả (${projects.length})`],
              ['RUNNING', 'Đang xử lý'],
              ['REVIEW', 'Chờ duyệt'],
              ['DONE', 'Hoàn thành'],
            ].map(([k, lbl]) => (
              <button
                key={k}
                type="button"
                className={`btn btn-sm ${filterMode === k ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setFilterMode(k)}
              >
                {lbl}
              </button>
            ))}
          </div>
        </div>

        {filteredProjects.length === 0 ? (
          <p style={{ fontSize: 13, color: '#9ca3af' }}>
            Chưa có dự án nào trong nhóm này.
          </p>
        ) : (
          <div style={{ display: 'grid', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
            {filteredProjects.map((p) => {
              const activeSel = p.id === activeProjectId;
              const lp = p.live_progress;
              return (
                <div
                  key={p.id}
                  onClick={() => onSelectProject(p.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 10,
                    padding: '10px 12px',
                    borderRadius: 8,
                    cursor: 'pointer',
                    background: activeSel ? 'var(--brand-soft)' : 'var(--bg-input)',
                    border: activeSel ? '1px solid #0ea5e9' : '1px solid var(--border)',
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        fontWeight: 600,
                        fontSize: 13.5,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                      }}
                    >
                      <ModeIcon mode={p.mode} />
                      <span
                        style={{
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {p.name}
                      </span>
                    </div>
                    {lp && RUNNING_STATES.includes(p.state) && (
                      <div style={{ fontSize: 11.5, color: '#7dd3fc', marginTop: 2 }}>
                        {lp.step_label ? `${lp.step_label} • ` : ''}
                        {lp.percent || 0}%{' '}
                        {lp.eta_sec !== null && lp.eta_sec !== undefined
                          ? `• Còn ~${formatSecondsVi(lp.eta_sec)}`
                          : ''}
                      </div>
                    )}
                  </div>
                  <span
                    className={`badge ${
                      p.state === 'COMPLETED'
                        ? 'badge-ok'
                        : p.state === 'PAUSED' || p.state === 'QUEUED'
                        ? 'badge-warn'
                        : 'badge-info'
                    }`}
                  >
                    {STAGE_LABELS[p.state] || p.state}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* SELECTED PROJECT DETAIL */}
      {detail && (
        <div className="card">
          <div className="page-header">
            <div>
              <div className="page-title">{detail.name}</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 5, flexWrap: 'wrap' }}>
                <span
                  className={`badge ${
                    detail.state === 'COMPLETED'
                      ? 'badge-ok'
                      : detail.state === 'PAUSED'
                      ? 'badge-warn'
                      : 'badge-info'
                  }`}
                >
                  {STAGE_LABELS[detail.state] || detail.state}
                </span>
                {detail.clips?.length > 0 && (
                  <span style={{ fontSize: 12.5, color: '#9ca3af' }}>
                    Đã xuất xong <strong>{completedClips.length}/{detail.clips.length}</strong> video
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {completedClips.length > 0 && (
                <a
                  href={studioApi.getProjectZipUrl(detail.id)}
                  download={`ShortVideo_${detail.id}.zip`}
                  className="btn btn-primary btn-sm"
                  style={{ textDecoration: 'none' }}
                  title="Tải trọn gói 1 tệp .ZIP gồm toàn bộ Video MP4, Ảnh bìa & Nội dung SEO"
                >
                  <Archive size={14} /> Tải trọn gói (.ZIP)
                </a>
              )}

              {canQuickEdit && detail.state !== 'AWAITING_REVIEW' && (
                <button
                  type="button"
                  className={`btn btn-sm ${quickEditOpen ? 'btn-primary' : 'btn-secondary'}`}
                  disabled={busyAction}
                  onClick={handleOpenQuickReEdit}
                >
                  <Edit3 size={14} /> {quickEditOpen ? 'Đóng khung chỉnh sửa' : 'Chỉnh sửa & Xuất lại nhanh'}
                </button>
              )}

              {isRunning && (
                <button
                  type="button"
                  className="btn btn-warn btn-sm"
                  disabled={busyAction}
                  onClick={handlePause}
                >
                  <Pause size={14} /> Tạm dừng
                </button>
              )}

              {canResume && (
                <button
                  type="button"
                  className="btn btn-success btn-sm"
                  disabled={busyAction}
                  onClick={handleResume}
                >
                  <Play size={14} /> Tiếp tục
                </button>
              )}

              {(isRunning || isPaused || detail.state === 'QUEUED') && (
                <button
                  type="button"
                  className="btn btn-danger btn-sm"
                  disabled={busyAction}
                  onClick={handleCancel}
                >
                  <Square size={13} /> Dừng hẳn
                </button>
              )}

              {completedClips.length > 0 && (
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => studioApi.openOutputFolder(detail.id)}
                >
                  <FolderOpen size={14} /> Mở thư mục
                </button>
              )}

              <button
                type="button"
                className="btn btn-danger btn-sm"
                disabled={busyAction}
                onClick={() => handleDeleteProject(detail.id)}
                title="Xóa khỏi danh sách dự án"
              >
                <Trash2 size={14} /> Xóa
              </button>
            </div>
          </div>

          {/* LIVE PROGRESS + ETA */}
          {(isRunning || isPaused || isInterruptedFromOldSession || detail.state === 'QUEUED') && (
            <div className="step-box" style={{ marginBottom: 16 }}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 10,
                  flexWrap: 'wrap',
                  marginBottom: 6,
                }}
              >
                <div style={{ fontSize: 13.2, fontWeight: 500 }}>
                  {isInterruptedFromOldSession
                    ? 'Dự án tạm dừng từ phiên trước — bấm nút Tiếp tục để xuất nốt các phần còn thiếu.'
                    : liveProgress?.message || STAGE_LABELS[detail.state]}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12.2, color: '#d1d5db' }}>
                  {liveProgress?.step_label && (
                    <span className="badge badge-info">{liveProgress.step_label}</span>
                  )}
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <Clock size={13} /> Đã chạy: <strong>{formatSecondsVi(liveProgress?.elapsed_sec || 0)}</strong>
                  </span>
                  <span style={{ color: '#34d399' }}>
                    Ước tính còn:{' '}
                    <strong>
                      {liveProgress?.eta_sec !== null && liveProgress?.eta_sec !== undefined
                        ? `~${formatSecondsVi(liveProgress.eta_sec)}`
                        : 'Đang tính...'}
                    </strong>
                  </span>
                  <strong>{pctVal}%</strong>
                </div>
              </div>

              <div className="progress-track" style={{ height: 9 }}>
                <div
                  className={`progress-fill ${isPaused ? 'paused' : ''}`}
                  style={{ width: `${Math.max(4, pctVal)}%` }}
                />
              </div>
            </div>
          )}

          {detail.state === 'FAILED' && (
            <div
              style={{
                padding: 12,
                borderRadius: 8,
                background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.4)',
                color: '#fca5a5',
                marginBottom: 14,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <AlertCircle size={16} />
              <span>Chi tiết lỗi: {detail.error_message}</span>
            </div>
          )}

          {/* REVIEW & QUICK RE-EDIT STUDIO (WITH PER-LINE SPEED/PITCH TUNING) */}
          {(detail.state === 'AWAITING_REVIEW' || quickEditOpen) && editableClips.length > 0 && (
            <div style={{ marginBottom: completedClips.length > 0 ? 16 : 0 }}>
              <div className="step-box" style={{ borderColor: '#0ea5e9' }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 10,
                    flexWrap: 'wrap',
                    gap: 8,
                  }}
                >
                  <strong style={{ fontSize: 13.8, color: '#7dd3fc' }}>
                    Biên tập kịch bản, chỉnh tốc độ/độ trầm từng câu, đổi chuyển cảnh & xuất lại nhanh
                  </strong>
                  {detail.state !== 'AWAITING_REVIEW' && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setQuickEditOpen(false)}
                    >
                      <X size={13} /> Thu gọn
                    </button>
                  )}
                </div>

                {/* Quick Visual, Aspect & Overlay Switches */}
                <div className="form-grid" style={{ marginBottom: 10 }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Chuyển cảnh mượt chuẩn CapCut</label>
                    <select
                      className="select"
                      value={layoutConfig.transition_style || 'CAPCUT_DISSOLVE'}
                      onChange={(e) => updateQuickLayout({ transition_style: e.target.value })}
                    >
                      <option value="CAPCUT_DISSOLVE">Mờ chồng êm ái (Mượt chuẩn CapCut)</option>
                      <option value="CAPCUT_SMOOTH_SLIDE">Lướt ngang mượt mà (Smooth Slide)</option>
                      <option value="CAPCUT_ZOOM_FLOW">Thu phóng mềm mại (Zoom Flow)</option>
                      <option value="CAPCUT_FLASH_BEAT">Chớp sáng tinh tế (Soft Flash)</option>
                      <option value="STATIC_LOOKBOOK">Đứng tĩnh 100% (Không zoom, không rung)</option>
                    </select>
                  </div>

                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Kiểu nền & tỷ lệ khung hình xuất</label>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {detail.mode === 'PRODUCT_SHOWCASE' && (
                        <select
                          className="select"
                          style={{ flex: 1 }}
                          value={layoutConfig.product_framing || 'BLURRED_STUDIO_CARD'}
                          onChange={(e) => updateQuickLayout({ product_framing: e.target.value })}
                        >
                          <option value="BLURRED_STUDIO_CARD">Thẻ nguyên vẹn + Nền mờ</option>
                          <option value="VELVET_DARK_LUXURY">Thẻ nguyên vẹn + Nền Đen Nhung</option>
                          <option value="FULL_BLEED_LUXURY">Phóng vừa tràn khung</option>
                        </select>
                      )}
                      <select
                        className="select"
                        style={{ width: detail.mode === 'PRODUCT_SHOWCASE' ? 126 : '100%' }}
                        value={layoutConfig.aspect_ratio || '9:16'}
                        onChange={(e) => updateQuickLayout({ aspect_ratio: e.target.value })}
                      >
                        <option value="9:16">9:16 TikTok/Shorts</option>
                        <option value="4:5">4:5 Facebook Feed</option>
                        <option value="1:1">1:1 Zalo Vuông</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Quick Overlay & Studio Switches */}
                <div
                  style={{
                    display: 'flex',
                    gap: 14,
                    flexWrap: 'wrap',
                    padding: '8px 10px',
                    borderRadius: 7,
                    background: 'var(--bg-panel)',
                    border: '1px solid var(--border)',
                    marginBottom: 12,
                  }}
                >
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.4, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={layoutConfig.show_top_banner !== false}
                      onChange={(e) => updateQuickLayout({ show_top_banner: e.target.checked })}
                    />
                    Hiện tiêu đề đầu
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.4, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={Boolean(layoutConfig.sales_badge_enabled)}
                      onChange={(e) => updateQuickLayout({ sales_badge_enabled: e.target.checked })}
                    />
                    Hiện nhãn giá/địa chỉ
                  </label>
                  {detail.mode === 'PRODUCT_SHOWCASE' && (
                    <>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.4, cursor: 'pointer', color: '#fde68a' }}>
                        <input
                          type="checkbox"
                          checked={Boolean(layoutConfig.studio_cutout_enabled)}
                          onChange={(e) => updateQuickLayout({ studio_cutout_enabled: e.target.checked })}
                        />
                        Tách nền Studio
                      </label>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.4, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={Boolean(layoutConfig.comparison_split_enabled)}
                          onChange={(e) => updateQuickLayout({ comparison_split_enabled: e.target.checked })}
                        />
                        Chia đôi so sánh A/B
                      </label>
                    </>
                  )}
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12.4, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={Boolean(layoutConfig.outro_card_enabled)}
                      onChange={(e) => updateQuickLayout({ outro_card_enabled: e.target.checked })}
                    />
                    Thẻ kết 2.5s cuối
                  </label>
                </div>

                {/* Reorder Product Media right inside Quick Re-Edit */}
                {detail.mode === 'PRODUCT_SHOWCASE' && editablePhotoList.length > 1 && (
                  <div style={{ marginBottom: 12 }}>
                    <div className="form-label">
                      Thứ tự trình chiếu ({editablePhotoList.length} mục — lên hình đủ 100%):
                    </div>
                    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
                      {editablePhotoList.map((ph, pIdx) => (
                        <div
                          key={`${ph.local_path}_${pIdx}`}
                          style={{
                            width: 78,
                            flexShrink: 0,
                            background: 'var(--bg-panel)',
                            border: '1px solid var(--border)',
                            borderRadius: 6,
                            padding: 4,
                            textAlign: 'center',
                          }}
                        >
                          {ph.isVideo ? (
                            <video
                              src={ph.media_url}
                              muted
                              style={{ width: '100%', height: 68, objectFit: 'contain', background: '#08090c', borderRadius: 4 }}
                            />
                          ) : (
                            <img
                              src={ph.media_url}
                              alt={`Mục ${pIdx + 1}`}
                              style={{
                                width: '100%',
                                height: 68,
                                objectFit: 'contain',
                                background: '#08090c',
                                borderRadius: 4,
                              }}
                            />
                          )}
                          <div style={{ fontSize: 10.5, color: '#d1d5db', margin: '2px 0' }}>
                            {ph.isVideo ? `Clip ${pIdx + 1}` : `Ảnh ${pIdx + 1}`}
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'center', gap: 3 }}>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              style={{ padding: '1px 4px', minHeight: 20 }}
                              disabled={pIdx === 0}
                              onClick={() => moveEditablePhoto(pIdx, pIdx - 1)}
                            >
                              <ArrowLeft size={11} />
                            </button>
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              style={{ padding: '1px 4px', minHeight: 20 }}
                              disabled={pIdx === editablePhotoList.length - 1}
                              onClick={() => moveEditablePhoto(pIdx, pIdx + 1)}
                            >
                              <ArrowRight size={11} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="form-grid" style={{ marginBottom: 12 }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Hình thức âm thanh & phụ đề khi xuất</label>
                    <select
                      className="select"
                      value={reviewAudioSubMode}
                      onChange={(e) => setReviewAudioSubMode(e.target.value)}
                    >
                      <option value="VIET_DUB_AND_SUB">Lồng tiếng + Phụ đề Việt</option>
                      <option value="VIET_DUB_NO_SUB">Chỉ Lồng tiếng Việt (Tắt chữ phụ đề)</option>
                      <option value="VIET_SUB_KEEP_ORIG">Chỉ ghép Phụ đề Việt (Giữ tiếng gốc)</option>
                      <option value="RAW_ORIGINAL">Giữ nguyên âm thanh gốc</option>
                    </select>
                  </div>

                  <InlineBgmSelector
                    bgmPresets={bgmPresets}
                    bgmPresetId={bgmPresetId}
                    onSelectPreset={setBgmPresetId}
                    bgmVolume={bgmVolume}
                    onVolumeChange={setBgmVolume}
                    customBgmPath={customBgmPath}
                    onCustomBgmChange={setCustomBgmPath}
                    notify={notify}
                  />
                </div>

                {(reviewAudioSubMode === 'VIET_DUB_AND_SUB' ||
                  reviewAudioSubMode === 'VIET_DUB_NO_SUB') && (
                  <div style={{ marginBottom: 12 }}>
                    <InlineVoiceSelector
                      voices={voices}
                      voiceId={selectedVoice}
                      onChange={setSelectedVoice}
                      voiceSpeed={globalVoiceSpeed}
                      onSpeedChange={setGlobalVoiceSpeed}
                      voicePitch={globalVoicePitch}
                      onPitchChange={setGlobalVoicePitch}
                      notify={notify}
                    />
                  </div>
                )}

                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 8,
                  }}
                >
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {detail.mode === 'MOVIE_CLIPPER' && (
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        disabled={translating}
                        onClick={handleTranslateAllToVi}
                      >
                        <Languages size={14} />{' '}
                        {translating ? 'Đang dịch...' : 'Dịch toàn bộ sang tiếng Việt'}
                      </button>
                    )}
                  </div>

                  <button
                    className="btn btn-success"
                    disabled={busyAction}
                    onClick={handleApproveAndRender}
                  >
                    <RefreshCw size={15} />{' '}
                    {detail.state === 'COMPLETED'
                      ? 'Xuất lại video với chỉnh sửa mới'
                      : `Xuất ${selectedParts.length}/${editableClips.length} phần đã chọn`}
                  </button>
                </div>
              </div>

              {editableClips.map((clip, cIdx) => {
                const isChecked = selectedParts.includes(clip.part_number);
                return (
                  <div
                    key={clip.clip_id}
                    className="step-box"
                    style={{
                      borderColor: isChecked ? '#0ea5e9' : 'var(--border)',
                      opacity: isChecked ? 1 : 0.65,
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        marginBottom: 8,
                      }}
                    >
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => togglePart(clip.part_number)}
                        />
                        Phần {clip.part_number} ({Math.round(clip.source_start_ms / 1000)}s –{' '}
                        {Math.round(clip.source_end_ms / 1000)}s)
                      </label>
                      <span style={{ fontSize: 12, color: '#9ca3af' }}>
                        {clip.lines.length} câu (có thể chỉnh tốc độ & độ trầm riêng từng câu)
                      </span>
                    </div>

                    {layoutConfig.show_top_banner !== false && (
                      <div className="form-group">
                        <label className="form-label">Tiêu đề đầu video</label>
                        <input
                          className="input"
                          value={clip.hook_banner_title}
                          onChange={(e) => handleBannerEdit(cIdx, e.target.value)}
                        />
                      </div>
                    )}

                    <div style={{ display: 'grid', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
                      {clip.lines.map((ln, lIdx) => {
                        const lKey = `${cIdx}_${lIdx}`;
                        const isPlayingThis = previewingLineKey === lKey;
                        return (
                          <div
                            key={ln.seq_index}
                            style={{
                              display: 'flex',
                              gap: 6,
                              alignItems: 'center',
                              flexWrap: 'wrap',
                              padding: '6px 8px',
                              borderRadius: 7,
                              background: 'var(--bg-panel)',
                              border: '1px solid var(--border)',
                            }}
                          >
                            <span style={{ fontSize: 11.2, color: '#9ca3af', minWidth: 40, fontWeight: 600 }}>
                              Câu {lIdx + 1}
                            </span>

                            {detail.mode === 'PRODUCT_SHOWCASE' &&
                              (ln.is_real_demo_slot ? (
                                <span className="badge badge-ok">Tiếng đàn / Clip mộc</span>
                              ) : (
                                detail.product_image_urls?.length > 0 && (
                                  <select
                                    className="select"
                                    style={{ width: 92, minHeight: 32, padding: '3px 7px', fontSize: 11.8 }}
                                    value={ln.matched_image_index ?? 0}
                                    onChange={(e) =>
                                      handleLinePatch(cIdx, lIdx, {
                                        matched_image_index: Number(e.target.value),
                                      })
                                    }
                                  >
                                    {detail.product_image_urls.map((_, pIdx) => (
                                      <option key={pIdx} value={pIdx}>
                                        Mục {pIdx + 1}
                                      </option>
                                    ))}
                                  </select>
                                )
                              ))}

                            <input
                              className="input"
                              style={{ flex: 1, minWidth: 190, minHeight: 32, padding: '4px 9px' }}
                              value={ln.vi_text}
                              onChange={(e) =>
                                handleLinePatch(cIdx, lIdx, { vi_text: e.target.value })
                              }
                            />

                            {!ln.is_real_demo_slot && (
                              <>
                                <select
                                  className="select"
                                  title="Tốc độ đọc riêng cho câu này"
                                  style={{ width: 92, minHeight: 32, padding: '3px 6px', fontSize: 11.5 }}
                                  value={ln.voice_speed_override === null ? '' : String(ln.voice_speed_override)}
                                  onChange={(e) =>
                                    handleLinePatch(cIdx, lIdx, {
                                      voice_speed_override:
                                        e.target.value === '' ? null : parseFloat(e.target.value),
                                    })
                                  }
                                >
                                  <option value="">Tốc độ chung</option>
                                  <option value="0.90">0.90x Chậm rãi</option>
                                  <option value="0.96">0.96x Điềm đạm</option>
                                  <option value="1.02">1.02x Tự nhiên</option>
                                  <option value="1.08">1.08x Linh hoạt</option>
                                  <option value="1.15">1.15x Nhịp nhanh</option>
                                </select>

                                <select
                                  className="select"
                                  title="Độ trầm ấm riêng cho câu này"
                                  style={{ width: 96, minHeight: 32, padding: '3px 6px', fontSize: 11.5 }}
                                  value={ln.voice_pitch_override === null ? '' : String(ln.voice_pitch_override)}
                                  onChange={(e) =>
                                    handleLinePatch(cIdx, lIdx, {
                                      voice_pitch_override:
                                        e.target.value === '' ? null : parseFloat(e.target.value),
                                    })
                                  }
                                >
                                  <option value="">Độ trầm chung</option>
                                  <option value="-2.8">-2.8 Trầm sâu</option>
                                  <option value="-1.4">-1.4 Ấm áp</option>
                                  <option value="0">0.0 Chuẩn</option>
                                  <option value="1.2">+1.2 Thanh sáng</option>
                                </select>

                                <button
                                  type="button"
                                  className={`btn btn-sm ${isPlayingThis ? 'btn-primary' : 'btn-secondary'}`}
                                  style={{ padding: '0 8px', minHeight: 32 }}
                                  title="Nghe thử riêng câu này"
                                  onClick={() => handlePreviewSingleLine(cIdx, lIdx, ln)}
                                >
                                  {isPlayingThis ? <Loader2 size={13} /> : <Volume2 size={13} />}
                                </button>
                              </>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* COMPLETED MULTIMEDIA PLAYERS & SEO */}
          {completedClips.length > 0 && (
            <div style={{ display: 'grid', gap: 14 }}>
              {completedClips.map((clip) => {
                let ytTags = [];
                let ttTags = [];
                try {
                  ytTags = JSON.parse(clip.seo?.yt_shorts_tags_json || '[]');
                  ttTags = JSON.parse(clip.seo?.tiktok_hashtags_json || '[]');
                } catch {
                  // ignore
                }
                const tiktokFull = `${clip.seo?.tiktok_caption || ''}\n${ttTags.join(' ')}`.trim();

                return (
                  <div key={clip.clip_id} className="result-clip-grid">
                    <div>
                      {clip.video_url && (
                        <video
                          controls
                          playsInline
                          src={`${clip.video_url}?t=${encodeURIComponent(detail.updated_at || '')}`}
                          poster={clip.cover_url || undefined}
                          style={{
                            width: '100%',
                            borderRadius: 8,
                            border: '1px solid var(--border)',
                            aspectRatio: videoCssAspect,
                            background: '#000',
                          }}
                        />
                      )}
                      <div style={{ display: 'grid', gap: 6, marginTop: 8 }}>
                        {clip.video_url && (
                          <a
                            href={clip.video_url}
                            download={`Video_Part_${clip.part_number}.mp4`}
                            className="btn btn-primary btn-sm"
                            style={{ width: '100%', textDecoration: 'none' }}
                          >
                            <Download size={14} /> Tải Video (.mp4)
                          </a>
                        )}
                        {clip.cover_url && (
                          <a
                            href={clip.cover_url}
                            download={`Anh_Bia_Part_${clip.part_number}.jpg`}
                            className="btn btn-secondary btn-sm"
                            style={{ width: '100%', textDecoration: 'none' }}
                          >
                            <Download size={14} /> Tải Ảnh Bìa
                          </a>
                        )}
                      </div>
                    </div>

                    <div style={{ minWidth: 0 }}>
                      <h4 style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>
                        Phần {clip.part_number}: {clip.hook_banner_title}
                      </h4>
                      <div
                        style={{
                          fontSize: 11.8,
                          color: '#9ca3af',
                          marginBottom: 8,
                          wordBreak: 'break-all',
                        }}
                      >
                        Đường dẫn: <code>{clip.output_mp4_path}</code>
                      </div>

                      {clip.seo && (
                        <>
                          <div className="seo-box">
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
                              <strong style={{ fontSize: 12.8 }}>Nội dung đăng YouTube Shorts</strong>
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() =>
                                    copyText(clip.seo.yt_shorts_title, 'tiêu đề Shorts')
                                  }
                                >
                                  <Copy size={13} /> Tiêu đề
                                </button>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => copyText(clip.seo.yt_shorts_desc, 'mô tả Shorts')}
                                >
                                  <Copy size={13} /> Mô tả
                                </button>
                              </div>
                            </div>
                            <div style={{ fontWeight: 600 }}>{clip.seo.yt_shorts_title}</div>
                            <div style={{ color: '#d1d5db', marginTop: 3, whiteSpace: 'pre-line' }}>
                              {clip.seo.yt_shorts_desc}
                            </div>
                            {ytTags.length > 0 && (
                              <div style={{ color: '#6b7280', marginTop: 4, fontSize: 11.5 }}>
                                Từ khóa: {ytTags.join(', ')}
                              </div>
                            )}
                          </div>

                          <div className="seo-box">
                            <div
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                gap: 8,
                                marginBottom: 6,
                              }}
                            >
                              <strong style={{ fontSize: 12.8 }}>Caption & Hashtag đăng TikTok</strong>
                              <button
                                className="btn btn-primary btn-sm"
                                onClick={() => copyText(tiktokFull, 'nội dung đăng TikTok')}
                              >
                                <Copy size={13} /> Sao chép đăng TikTok
                              </button>
                            </div>
                            <div style={{ whiteSpace: 'pre-line', color: '#e5e7eb' }}>
                              {tiktokFull}
                            </div>
                          </div>

                          {clip.seo.pinned_comment && (
                            <div className="seo-box">
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  gap: 8,
                                  marginBottom: 6,
                                }}
                              >
                                <strong style={{ fontSize: 12.8, color: '#34d399' }}>
                                  Bình luận đầu tiên gợi ý ghim dưới video
                                </strong>
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() =>
                                    copyText(clip.seo.pinned_comment, 'bình luận ghim')
                                  }
                                >
                                  <Copy size={13} /> Sao chép
                                </button>
                              </div>
                              <div style={{ whiteSpace: 'pre-line', color: '#d1fae5' }}>
                                {clip.seo.pinned_comment}
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
