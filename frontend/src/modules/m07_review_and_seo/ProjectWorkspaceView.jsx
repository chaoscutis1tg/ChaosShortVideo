import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  Archive,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  Columns,
  Copy,
  Download,
  Edit3,
  FileText,
  Film,
  FolderKanban,
  FolderOpen,
  FolderPlus,
  FolderTree,
  ImagePlus,
  Languages,
  Loader2,
  MessageSquareText,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShoppingBag,
  Square,
  Terminal,
  Trash2,
  Volume2,
  Wand2,
  X,
} from 'lucide-react';
import { studioApi } from '../m00_core_contracts/apiClient';
import {
  copyTextSafe,
  DEFAULT_LAYOUT_CONFIG,
  formatSecondsVi,
  STAGE_LABELS,
} from '../m00_core_contracts/constants';
import {
  GROUP_COLOR_PALETTE,
  InlineBgmSelector,
  InlineVoiceSelector,
  SwitchCard,
} from '../m00_core_contracts/StudioWidgets';

const RUNNING_STATES = [
  'QUEUED',
  'INGESTING',
  'TRANSCRIBING_GPU',
  'AI_ANALYZING',
  'GENERATING_ASSETS',
  'RENDERING_NVENC',
  'PACKAGING_SEO',
];

const MODE_LABELS = {
  MOVIE_CLIPPER: 'Cắt & Dịch Video',
  PRODUCT_SHOWCASE: 'Video Bán Hàng',
  TOPIC_VIDEO: 'Tạo Từ Chủ Đề',
  TOPIC_TO_SHORTS: 'Tạo Từ Chủ Đề',
  THREADS_TOPIC: 'Threads & Bình Luận',
};

function ModeIcon({ mode }) {
  if (mode === 'MOVIE_CLIPPER') return <Film size={15} strokeWidth={1.9} />;
  if (mode === 'PRODUCT_SHOWCASE') return <ShoppingBag size={15} strokeWidth={1.9} />;
  if (mode === 'THREADS_TOPIC') return <MessageSquareText size={15} strokeWidth={1.9} />;
  return <FileText size={15} strokeWidth={1.9} />;
}

/**
 * Estimates spoken Vietnamese narration duration (seconds) from text word count & speed rate.
 */
function estimateSpokenSeconds(text, speedRate = 1.02) {
  const clean = (text || '').trim();
  if (!clean) return 0;
  const words = clean.split(/\s+/).filter(Boolean).length;
  const safeSpeed = Math.max(0.75, Number(speedRate) || 1.02);
  return Math.max(1.1, words / (2.85 * safeSpeed));
}

const LiveElapsedReadout = React.memo(function LiveElapsedReadout({
  baseElapsedSec,
  baseEtaSec,
  anchorRef,
  isRunning,
}) {
  const [offsetSec, setOffsetSec] = useState(0);

  useEffect(() => {
    setOffsetSec(0);
    if (!isRunning) return undefined;
    const t = setInterval(() => {
      const diff = Math.max(0, Math.floor((Date.now() - (anchorRef.current || Date.now())) / 1000));
      setOffsetSec(diff);
    }, 1000);
    return () => clearInterval(t);
  }, [baseElapsedSec, baseEtaSec, isRunning]);

  const realElapsed = (baseElapsedSec || 0) + (isRunning ? offsetSec : 0);
  const realEta =
    baseEtaSec !== null && baseEtaSec !== undefined
      ? Math.max(1, baseEtaSec - (isRunning ? offsetSec : 0))
      : null;

  return (
    <>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <Clock size={13} /> Đã chạy: <strong>{formatSecondsVi(realElapsed)}</strong>
      </span>
      <span style={{ color: 'var(--success-text)' }}>
        Ước tính còn:{' '}
        <strong>
          {realEta !== null ? `~${formatSecondsVi(realEta)}` : 'Đang đo tốc độ thực...'}
        </strong>
      </span>
    </>
  );
});

export default function ProjectWorkspaceView({
  activeProjectId,
  projects,
  projectGroups = [],
  activeGroupId = 'ALL',
  onSelectGroup,
  onGroupsChanged,
  onSelectProject,
  onProjectsRefresh,
  voices,
  bgmPresets,
  layoutConfig,
  setLayoutConfig,
  onPreviewFrameReady,
  onQuickEditStateChange,
  notify,
}) {
  const [filterMode, setFilterMode] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDesc, setNewGroupDesc] = useState('');
  const [newGroupColor, setNewGroupColor] = useState(GROUP_COLOR_PALETTE[0]);
  const [savingGroup, setSavingGroup] = useState(false);

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
  const [pubNoteDraft, setPubNoteDraft] = useState('');
  const [savingPubStatus, setSavingPubStatus] = useState(false);
  const [consoleExpanded, setConsoleExpanded] = useState(true);
  const progressAnchorMonoRef = useRef(Date.now());
  const consoleBodyRef = useRef(null);

  const groupMap = useMemo(() => {
    const map = {};
    for (const g of projectGroups) {
      map[g.group_id] = g;
    }
    return map;
  }, [projectGroups]);

  const ungroupedCount = useMemo(
    () => projects.filter((p) => !p.parent_group_id || !groupMap[p.parent_group_id]).length,
    [projects, groupMap]
  );

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
          stock_keywords: (() => {
            try {
              return JSON.parse(ln.stock_keywords_json || '[]');
            } catch {
              return [];
            }
          })(),
          matched_image_index:
            ln.matched_image_index !== undefined ? ln.matched_image_index : null,
          is_real_demo_slot: Boolean(ln.is_real_demo_slot),
          callout_label: ln.callout_label || '',
          voice_profile_override: ln.voice_profile_override || null,
          speaker_handle: ln.speaker_handle || '',
          speaker_avatar_path: ln.speaker_avatar_path || '',
          display_card_text: ln.display_card_text || '',
          likes_display: ln.likes_display || '',
          card_image_path: ln.card_image_path || '',
          is_op_post: Boolean(ln.is_op_post),
          voice_speed_override:
            ln.voice_speed_override !== undefined && ln.voice_speed_override !== null
              ? Number(ln.voice_speed_override)
              : null,
          voice_pitch_override:
            ln.voice_pitch_override !== undefined && ln.voice_pitch_override !== null
              ? Number(ln.voice_pitch_override)
              : null,
          motion_spec: (() => {
            try {
              return ln.motion_spec_json ? JSON.parse(ln.motion_spec_json) : null;
            } catch {
              return null;
            }
          })(),
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
      if (forceRebuildEditor) {
        setPubNoteDraft(d.published_note || '');
      }
      if (d.live_progress) {
        progressAnchorMonoRef.current = Date.now();
      }
      setLiveProgress(d.live_progress || null);

      // Smart Preview Frame Sync: load cover/preview into the 9:16 Inspector so it's never blank!
      if (onPreviewFrameReady) {
        const firstCover = (d.clips || []).find((c) => c.cover_url)?.cover_url;
        const bestPreview =
          firstCover ||
          d.source_media?.preview_urls?.[0] ||
          d.product_image_urls?.[0] ||
          '';
        onPreviewFrameReady(bestPreview);
      }
    } catch {
      // ignore
    }
  };

  // Notify App.jsx when Quick Re-Edit / Review is open so Right 9:16 Inspector opens contextually
  useEffect(() => {
    const editorVisible = Boolean(
      detail && (detail.state === 'AWAITING_REVIEW' || quickEditOpen)
    );
    if (onQuickEditStateChange) {
      onQuickEditStateChange(editorVisible, detail?.mode || null);
    }
  }, [detail?.id, detail?.state, detail?.mode, quickEditOpen]);

  useEffect(() => {
    return () => {
      if (onQuickEditStateChange) onQuickEditStateChange(false, null);
    };
  }, []);

  // Load detail & subscribe to live WebSocket updates when activeProjectId changes
  useEffect(() => {
    setSelectedParts([]);
    setQuickEditOpen(false);
    if (!activeProjectId) {
      setDetail(null);
      return;
    }
    loadDetail(activeProjectId, true);

    let wsConnected = false;
    const ws = studioApi.connectProgressSocket(activeProjectId, (ev) => {
      wsConnected = true;
      progressAnchorMonoRef.current = Date.now();
      setLiveProgress(ev);
      if (['AWAITING_REVIEW', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED'].includes(ev.stage)) {
        loadDetail(activeProjectId, ev.stage === 'AWAITING_REVIEW');
      }
    });
    ws.onopen = () => {
      wsConnected = true;
    };
    ws.onclose = () => {
      wsConnected = false;
    };

    const fallbackPoll = setInterval(() => {
      if (!document.hidden && !wsConnected) {
        loadDetail(activeProjectId, false);
      }
    }, 5000);

    return () => {
      clearInterval(fallbackPoll);
      ws.close();
    };
  }, [activeProjectId]);

  // Lightweight state-sync fallback only every 9s while running (WebSocket handles sub-second progress!)
  useEffect(() => {
    if (!activeProjectId || !detail || !RUNNING_STATES.includes(detail.state)) {
      return undefined;
    }
    const pollTimer = setInterval(() => {
      if (!document.hidden) {
        loadDetail(activeProjectId, false);
      }
    }, 9000);
    return () => {
      clearInterval(pollTimer);
    };
  }, [activeProjectId, detail?.state, detail?.is_active_in_memory]);

  useEffect(() => {
    if (consoleExpanded && consoleBodyRef.current) {
      consoleBodyRef.current.scrollTop = consoleBodyRef.current.scrollHeight;
    }
  }, [liveProgress?.logs?.length, liveProgress?.message, consoleExpanded]);

  const filteredProjects = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return projects.filter((p) => {
      if (activeGroupId === 'UNGROUPED') {
        if (p.parent_group_id && groupMap[p.parent_group_id]) return false;
      } else if (activeGroupId && activeGroupId !== 'ALL') {
        if (p.parent_group_id !== activeGroupId) return false;
      }

      if (filterMode === 'RUNNING') {
        if (!RUNNING_STATES.includes(p.state) && p.state !== 'PAUSED') return false;
      } else if (filterMode === 'REVIEW') {
        if (p.state !== 'AWAITING_REVIEW') return false;
      } else if (filterMode === 'DONE') {
        if (p.state !== 'COMPLETED') return false;
      } else if (filterMode === 'UNPOSTED') {
        if (p.state !== 'COMPLETED') return false;
        if (Array.isArray(p.published_channels) && p.published_channels.length > 0) return false;
      } else if (filterMode === 'POSTED') {
        if (!Array.isArray(p.published_channels) || p.published_channels.length === 0) return false;
      }

      if (q) {
        const hay = `${p.name || ''} ${MODE_LABELS[p.mode] || p.mode || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [projects, activeGroupId, groupMap, filterMode, searchQuery]);

  // Auto-select first matching project if current selection is missing from filtered list
  useEffect(() => {
    if (
      filteredProjects.length > 0 &&
      (!activeProjectId || !filteredProjects.some((p) => p.id === activeProjectId))
    ) {
      onSelectProject(filteredProjects[0].id);
    }
  }, [filteredProjects, activeProjectId]);

  const handleCreateParentGroup = async () => {
    const clean = newGroupName.trim();
    if (clean.length < 2) {
      notify('Vui lòng nhập tên Dự Án Cha (ít nhất 2 ký tự).');
      return;
    }
    setSavingGroup(true);
    try {
      const saved = await studioApi.saveProjectGroup({
        name: clean,
        description: newGroupDesc.trim(),
        color_tag: newGroupColor,
      });
      setNewGroupName('');
      setNewGroupDesc('');
      setCreatingGroup(false);
      if (onGroupsChanged) await onGroupsChanged();
      if (onSelectGroup) onSelectGroup(saved.group_id);
      notify(`Đã tạo Dự Án Cha "${saved.name}".`);
    } catch (err) {
      notify(`Lỗi tạo Dự Án Cha: ${err.message}`);
    } finally {
      setSavingGroup(false);
    }
  };

  const handleDeleteParentGroup = async (grp) => {
    try {
      await studioApi.deleteProjectGroup(grp.group_id);
      if (activeGroupId === grp.group_id && onSelectGroup) {
        onSelectGroup('ALL');
      }
      if (onGroupsChanged) await onGroupsChanged();
      if (detail?.parent_group_id === grp.group_id) {
        setDetail((prev) => (prev ? { ...prev, parent_group_id: null } : prev));
      }
      notify(
        `Đã xóa Dự Án Cha "${grp.name}" (các dự án con vẫn được giữ nguyên an toàn).`
      );
    } catch (err) {
      notify(`Lỗi xóa Dự Án Cha: ${err.message}`);
    }
  };

  const handleAssignDetailGroup = async (nextGroupId) => {
    if (!detail) return;
    const cleanVal = nextGroupId || null;
    try {
      await studioApi.assignProjectGroup(detail.id, cleanVal);
      setDetail((prev) => (prev ? { ...prev, parent_group_id: cleanVal } : prev));
      if (onGroupsChanged) await onGroupsChanged();
      notify(
        cleanVal
          ? `Đã chuyển dự án vào Dự Án Cha "${groupMap[cleanVal]?.name || ''}".`
          : 'Đã gỡ dự án khỏi Dự Án Cha.'
      );
    } catch (err) {
      notify(`Lỗi phân nhóm: ${err.message}`);
    }
  };

  const handleTogglePublishedChannel = async (channelKey) => {
    if (!detail || savingPubStatus) return;
    const curList = Array.isArray(detail.published_channels) ? detail.published_channels : [];
    const nextList = curList.includes(channelKey)
      ? curList.filter((c) => c !== channelKey)
      : [...curList, channelKey];
    setSavingPubStatus(true);
    try {
      const saved = await studioApi.updateProjectPublishStatus(
        detail.id,
        nextList,
        pubNoteDraft.trim()
      );
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              published_channels: saved.published_channels || nextList,
              published_note: saved.published_note ?? pubNoteDraft.trim(),
            }
          : prev
      );
      if (onProjectsRefresh) onProjectsRefresh();
      const chNames = {
        TIKTOK: 'TikTok',
        YOUTUBE_SHORTS: 'YouTube Shorts',
        FACEBOOK_REELS: 'Facebook / Reels',
      };
      notify(
        nextList.includes(channelKey)
          ? `Đã đánh dấu ĐÃ ĐĂNG lên ${chNames[channelKey] || channelKey}!`
          : `Đã bỏ đánh dấu đăng ${chNames[channelKey] || channelKey}.`
      );
    } catch (err) {
      notify(`Lỗi lưu trạng thái đăng kênh: ${err.message}`);
    } finally {
      setSavingPubStatus(false);
    }
  };

  const handleSavePublishNote = async () => {
    if (!detail || savingPubStatus) return;
    const curList = Array.isArray(detail.published_channels) ? detail.published_channels : [];
    setSavingPubStatus(true);
    try {
      const saved = await studioApi.updateProjectPublishStatus(
        detail.id,
        curList,
        pubNoteDraft.trim()
      );
      setDetail((prev) =>
        prev ? { ...prev, published_note: saved.published_note ?? pubNoteDraft.trim() } : prev
      );
      if (onProjectsRefresh) onProjectsRefresh();
      notify('Đã lưu ghi chú lịch / link bài đăng kênh.');
    } catch (err) {
      notify(`Lỗi lưu ghi chú đăng kênh: ${err.message}`);
    } finally {
      setSavingPubStatus(false);
    }
  };

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
      setDetail(null);
      if (onProjectsRefresh) await onProjectsRefresh();
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
    if (isDubbed) {
      const hasEmptyLine = editableClips
        .filter((c) => selectedParts.includes(c.part_number))
        .some((c) =>
          (c.lines || []).some((ln) => !ln.is_real_demo_slot && !(ln.vi_text || '').trim())
        );
      if (hasEmptyLine) {
        notify('Vui lòng không để trống câu lời đọc tiếng Việt trong phần đã chọn xuất.');
        return;
      }
    }
    const effSubStyle =
      reviewAudioSubMode === 'VIET_DUB_NO_SUB' || reviewAudioSubMode === 'RAW_ORIGINAL'
        ? 'NONE'
        : detail.mode === 'THREADS_TOPIC'
        ? detail.saved_request?.subtitle_style || 'NONE'
        : isMovie || detail.mode === 'PRODUCT_SHOWCASE'
        ? 'CINEMA'
        : 'KARAOKE_CAPCUT';

    setBusyAction(true);
    try {
      await studioApi.renderApprovedProject(detail.id, {
        voice_profile_id: selectedVoice,
        visual_mode: detail.saved_request?.visual_mode || 'AI_IMAGE',
        bgm_preset_id: bgmPresetId,
        custom_bgm_path: customBgmPath,
        audio_config: {
          enable_narration: isDubbed,
          keep_original_audio:
            isMovie ||
            (detail.mode === 'THREADS_TOPIC' && Boolean(detail.saved_request?.keep_bg_audio)),
          ducking_ratio:
            detail.mode === 'THREADS_TOPIC'
              ? Number(detail.saved_request?.bg_audio_volume ?? 0.14)
              : 0.18,
          bgm_path: null,
          bgm_volume: bgmVolume,
          subtitle_style: effSubStyle,
          subtitle_pos_y: layoutConfig.subtitle_pos_y ?? 0.84,
          subtitle_font_size: layoutConfig.subtitle_font_size ?? 52,
          voice_speed_global: Number(globalVoiceSpeed),
          voice_pitch_global: Number(globalVoicePitch),
          enable_card_pop_sfx:
            detail.mode === 'THREADS_TOPIC'
              ? detail.saved_request?.enable_card_pop_sfx !== false
              : false,
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

  const activeGroupObj =
    activeGroupId && activeGroupId !== 'ALL' && activeGroupId !== 'UNGROUPED'
      ? groupMap[activeGroupId]
      : null;

  return (
    <div>
      {/* PARENT PROJECT CONTAINERS STRIP (DỰ ÁN CHA CHỨA CÁC DỰ ÁN CON) */}
      <div className="parent-groups-strip">
        <span
          style={{
            fontSize: 12.4,
            fontWeight: 800,
            color: 'var(--text-primary)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            whiteSpace: 'nowrap',
            marginRight: 4,
          }}
        >
          <FolderTree size={15} style={{ color: 'var(--brand-text)' }} />
          Dự Án Cha:
        </span>

        <button
          type="button"
          className={`group-chip ${activeGroupId === 'ALL' ? 'active' : ''}`}
          onClick={() => onSelectGroup && onSelectGroup('ALL')}
        >
          <span>Tất cả ({projects.length})</span>
        </button>

        <button
          type="button"
          className={`group-chip ${activeGroupId === 'UNGROUPED' ? 'active' : ''}`}
          onClick={() => onSelectGroup && onSelectGroup('UNGROUPED')}
        >
          <span>Độc lập ({ungroupedCount})</span>
        </button>

        {projectGroups.map((grp) => {
          const isAct = activeGroupId === grp.group_id;
          return (
            <div
              key={grp.group_id}
              className={`group-chip ${isAct ? 'active' : ''}`}
              onClick={() => onSelectGroup && onSelectGroup(grp.group_id)}
              title={grp.description || `Dự Án Cha: ${grp.name}`}
            >
              <span
                className="group-dot"
                style={{ background: grp.color_tag || '#0ea5e9' }}
              />
              <span>
                {grp.name} ({grp.project_count || 0})
              </span>
              {isAct && (
                <button
                  type="button"
                  title={`Xóa Dự Án Cha "${grp.name}" (giữ nguyên các dự án con)`}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteParentGroup(grp);
                  }}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--danger)',
                    cursor: 'pointer',
                    padding: 0,
                    marginLeft: 2,
                    display: 'inline-flex',
                    alignItems: 'center',
                  }}
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          );
        })}

        <button
          type="button"
          className={`btn btn-sm ${creatingGroup ? 'btn-primary' : 'btn-secondary'}`}
          style={{ marginLeft: 'auto', whiteSpace: 'nowrap', flexShrink: 0 }}
          onClick={() => setCreatingGroup((p) => !p)}
        >
          {creatingGroup ? (
            <>
              <X size={13} /> Đóng
            </>
          ) : (
            <>
              <FolderPlus size={14} /> + Tạo Dự Án Cha
            </>
          )}
        </button>
      </div>

      {/* INLINE PARENT GROUP CREATOR */}
      {creatingGroup && (
        <div
          className="card"
          style={{
            marginBottom: 14,
            padding: '14px 16px',
            borderColor: 'var(--brand)',
          }}
        >
          <div
            style={{
              fontWeight: 700,
              fontSize: 13.6,
              color: 'var(--brand-text)',
              marginBottom: 8,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <FolderPlus size={15} /> Tạo Dự Án Cha mới để gom quản lý nhiều dự án video con (Series / Chiến dịch / Khách hàng)
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              className="input"
              style={{ flex: 1, minWidth: 220, minHeight: 37 }}
              placeholder="Tên Dự Án Cha (VD: Series Học Guitar 30 Ngày / Bộ sưu tập Đàn Violin S2...)"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateParentGroup()}
            />
            <input
              className="input"
              style={{ flex: 1, minWidth: 190, minHeight: 37 }}
              placeholder="Ghi chú ngắn (tùy chọn)"
              value={newGroupDesc}
              onChange={(e) => setNewGroupDesc(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreateParentGroup()}
            />
            <div style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              {GROUP_COLOR_PALETTE.map((hex) => (
                <button
                  key={hex}
                  type="button"
                  onClick={() => setNewGroupColor(hex)}
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: 999,
                    background: hex,
                    border: newGroupColor === hex ? '2.5px solid #ffffff' : '1px solid var(--border)',
                    boxShadow: newGroupColor === hex ? `0 0 0 2px ${hex}` : 'none',
                    cursor: 'pointer',
                  }}
                />
              ))}
            </div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              style={{ minHeight: 37 }}
              disabled={savingGroup}
              onClick={handleCreateParentGroup}
            >
              <Plus size={14} /> {savingGroup ? 'Đang tạo...' : 'Lưu Dự Án Cha'}
            </button>
          </div>
        </div>
      )}

      {/* 2-COLUMN MASTER-DETAIL WORKSPACE (NO MORE JUMPING UP & DOWN!) */}
      <div className="workspace-split-2col">
        {/* LEFT STICKY MASTER PANE */}
        <div className="workspace-master-pane">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 6,
              marginBottom: 8,
            }}
          >
            <div
              style={{
                fontWeight: 800,
                fontSize: 14.2,
                color: 'var(--text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                minWidth: 0,
              }}
            >
              <FolderKanban size={17} style={{ color: 'var(--brand-text)', flexShrink: 0 }} />
              <span
                style={{
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {activeGroupObj ? activeGroupObj.name : 'Danh sách Dự Án'}
              </span>
            </div>
            <span className="badge badge-info" style={{ fontSize: 11, padding: '2px 8px' }}>
              {filteredProjects.length} mục
            </span>
          </div>

          {/* INSTANT SEARCH INPUT */}
          <div style={{ position: 'relative', marginBottom: 8 }}>
            <Search
              size={14}
              style={{
                position: 'absolute',
                left: 11,
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)',
              }}
            />
            <input
              className="input"
              style={{
                minHeight: 35,
                padding: '6px 30px 6px 32px',
                fontSize: 12.8,
              }}
              placeholder="Tìm nhanh theo tên dự án..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                style={{
                  position: 'absolute',
                  right: 8,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  padding: 2,
                  display: 'inline-flex',
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* STATUS FILTER PILLS */}
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {[
              ['ALL', 'Tất cả'],
              ['RUNNING', 'Đang chạy'],
              ['REVIEW', 'Chờ duyệt'],
              ['DONE', 'Hoàn thành'],
              ['UNPOSTED', 'Chưa đăng kênh'],
              ['POSTED', 'Đã đăng'],
            ].map(([k, lbl]) => (
              <button
                key={k}
                type="button"
                onClick={() => setFilterMode(k)}
                style={{
                  padding: '4px 9px',
                  borderRadius: 999,
                  fontSize: 11.5,
                  fontWeight: filterMode === k ? 700 : 500,
                  cursor: 'pointer',
                  border:
                    filterMode === k ? '1px solid var(--brand)' : '1px solid var(--border)',
                  background: filterMode === k ? 'var(--brand-soft)' : 'var(--bg-step)',
                  color: filterMode === k ? 'var(--brand-text)' : 'var(--text-secondary)',
                }}
              >
                {lbl}
              </button>
            ))}
          </div>

          {/* INDEPENDENTLY SCROLLING PROJECT ROWS */}
          <div className="workspace-master-list">
            {filteredProjects.length === 0 ? (
              <div
                className="step-box"
                style={{ marginBottom: 0, textAlign: 'center', padding: '22px 12px' }}
              >
                <div className="text-sub" style={{ fontSize: 13 }}>
                  Không có dự án nào khớp bộ lọc hiện tại.
                </div>
              </div>
            ) : (
              filteredProjects.map((p) => {
                const activeSel = p.id === activeProjectId;
                const lp = p.live_progress;
                const parentGrp = p.parent_group_id ? groupMap[p.parent_group_id] : null;
                return (
                  <div
                    key={p.id}
                    onClick={() => onSelectProject(p.id)}
                    className={`project-row-item ${activeSel ? 'active' : ''}`}
                    style={{ padding: '10px 12px', alignItems: 'flex-start' }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: 13.4,
                          color: 'var(--text-primary)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 7,
                        }}
                      >
                        <span
                          style={{
                            color: 'var(--brand-text)',
                            display: 'inline-flex',
                            flexShrink: 0,
                          }}
                        >
                          <ModeIcon mode={p.mode} />
                        </span>
                        <span
                          style={{
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                          title={p.name}
                        >
                          {p.name}
                        </span>
                      </div>

                      <div
                        className="text-muted"
                        style={{
                          fontSize: 11.6,
                          marginTop: 4,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          flexWrap: 'wrap',
                        }}
                      >
                        <span>{MODE_LABELS[p.mode] || p.mode}</span>
                        {parentGrp && (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                              padding: '1px 7px',
                              borderRadius: 999,
                              background: 'var(--bg-elevated)',
                              border: '1px solid var(--border)',
                              color: 'var(--text-secondary)',
                              fontWeight: 600,
                            }}
                          >
                            <span
                              className="group-dot"
                              style={{
                                width: 7,
                                height: 7,
                                background: parentGrp.color_tag || '#0ea5e9',
                              }}
                            />
                            {parentGrp.name}
                          </span>
                        )}
                        {Array.isArray(p.published_channels) && p.published_channels.length > 0 && (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 3,
                              padding: '1px 6px',
                              borderRadius: 999,
                              background: 'rgba(16, 185, 129, 0.14)',
                              border: '1px solid rgba(16, 185, 129, 0.4)',
                              color: 'var(--success-text)',
                              fontSize: 10.4,
                              fontWeight: 700,
                            }}
                            title={`Đã đăng: ${p.published_channels.join(', ')}`}
                          >
                            <CheckCircle2 size={10} /> Đã đăng ({p.published_channels.length})
                          </span>
                        )}
                      </div>

                      {lp && RUNNING_STATES.includes(p.state) && (
                        <div
                          style={{
                            fontSize: 11.5,
                            marginTop: 4,
                            color: 'var(--brand-text)',
                            fontWeight: 600,
                          }}
                        >
                          {lp.step_label ? `${lp.step_label} • ` : ''}
                          {lp.percent || 0}%
                          {lp.eta_sec !== null && lp.eta_sec !== undefined
                            ? ` • Còn ~${formatSecondsVi(lp.eta_sec)}`
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
                      style={{ fontSize: 10.8, padding: '2px 7px', flexShrink: 0 }}
                    >
                      {STAGE_LABELS[p.state] || p.state}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT DETAIL PANE */}
        <div className="workspace-detail-pane">
          {!detail ? (
            <div className="card" style={{ textAlign: 'center', padding: '44px 24px' }}>
              <FolderKanban
                size={34}
                style={{ color: 'var(--brand-text)', margin: '0 auto 10px', display: 'block' }}
              />
              <div style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 4 }}>
                Chọn một dự án ở cột bên trái để xem video &amp; bộ nội dung SEO
              </div>
              <div className="text-sub" style={{ fontSize: 13.2 }}>
                Bạn cũng có thể gom các dự án con vào cùng một Dự Án Cha ở thanh phía trên để quản lý theo Series dễ dàng.
              </div>
            </div>
          ) : (
            <div className="card" style={{ marginBottom: 0 }}>
              <div className="page-header">
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="page-title" style={{ wordBreak: 'break-word' }}>
                    {detail.name}
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                      marginTop: 7,
                      flexWrap: 'wrap',
                    }}
                  >
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
                    <span className="badge">{MODE_LABELS[detail.mode] || detail.mode}</span>
                    <span className="badge" style={{ fontSize: 11.2 }}>
                      {savedAspect}
                    </span>
                    {detail.saved_request?.visual_mode === 'MOTION_GRAPHICS' && (
                      <span className="badge badge-ok" style={{ fontSize: 11.2 }}>
                        🎬 Motion Graphics
                      </span>
                    )}
                    {detail.mode === 'THREADS_TOPIC' &&
                      detail.saved_request?.layout_config?.threads_card_theme ===
                        'MIDNIGHT_VINYL_LYRIC' && (
                        <span className="badge badge-info" style={{ fontSize: 11.2 }}>
                          🎵 Đĩa Than Vinyl
                        </span>
                      )}
                    {detail.mode === 'THREADS_TOPIC' &&
                      detail.saved_request?.layout_config?.threads_card_theme ===
                        'QUIZ_COUNTDOWN_CARD' && (
                        <span className="badge badge-info" style={{ fontSize: 11.2 }}>
                          ⏱ Đố Vui 3-2-1
                        </span>
                      )}
                    {detail.saved_request?.layout_config?.ambience_overlay &&
                      detail.saved_request.layout_config.ambience_overlay !== 'NONE' && (
                        <span className="badge badge-ok" style={{ fontSize: 11.2 }}>
                          ✨ {detail.saved_request.layout_config.ambience_overlay}
                        </span>
                      )}
                    {detail.saved_request?.layout_config?.story_progress_bar_enabled && (
                      <span className="badge badge-info" style={{ fontSize: 11.2 }}>
                        Thanh đốt truyện
                      </span>
                    )}
                    {detail.clips?.length > 0 && (
                      <span className="text-sub" style={{ fontSize: 12.8 }}>
                        Đã xuất xong{' '}
                        <strong>
                          {completedClips.length}/{detail.clips.length}
                        </strong>{' '}
                        video
                      </span>
                    )}

                    {/* ASSIGN / MOVE CHILD PROJECT TO PARENT PROJECT CONTAINER */}
                    <div
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        marginLeft: 4,
                      }}
                    >
                      <FolderTree size={13} style={{ color: 'var(--brand-text)' }} />
                      <select
                        className="select"
                        style={{
                          width: 'auto',
                          minWidth: 185,
                          minHeight: 31,
                          padding: '3px 9px',
                          fontSize: 12.2,
                        }}
                        value={detail.parent_group_id || ''}
                        onChange={(e) => handleAssignDetailGroup(e.target.value)}
                        title="Gắn hoặc chuyển dự án con này sang Dự Án Cha khác"
                      >
                        <option value="">Dự án độc lập (Chưa gắn Dự Án Cha)</option>
                        {projectGroups.map((g) => (
                          <option key={g.group_id} value={g.group_id}>
                            Dự Án Cha: {g.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* CHANNEL PUBLISHING TRACKER (ĐÃ ĐĂNG TIKTOK / YOUTUBE SHORTS / REELS) */}
                  <div
                    style={{
                      display: 'flex',
                      gap: 6,
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      marginTop: 9,
                      padding: '7px 10px',
                      borderRadius: 9,
                      background: 'var(--bg-step)',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    <span style={{ fontSize: 11.8, fontWeight: 700, color: 'var(--text-secondary)' }}>
                      Trạng thái đăng kênh:
                    </span>
                    {[
                      ['TIKTOK', 'TikTok'],
                      ['YOUTUBE_SHORTS', 'YouTube Shorts'],
                      ['FACEBOOK_REELS', 'Reels / FB'],
                    ].map(([chKey, chLabel]) => {
                      const isPosted = (detail.published_channels || []).includes(chKey);
                      return (
                        <button
                          key={chKey}
                          type="button"
                          disabled={savingPubStatus}
                          onClick={() => handleTogglePublishedChannel(chKey)}
                          className={`btn btn-sm ${isPosted ? 'btn-primary' : 'btn-secondary'}`}
                          style={{
                            minHeight: 27,
                            padding: '2px 9px',
                            fontSize: 11.5,
                            background: isPosted ? 'rgba(16, 185, 129, 0.22)' : undefined,
                            borderColor: isPosted ? 'rgba(16, 185, 129, 0.65)' : undefined,
                            color: isPosted ? 'var(--success-text)' : undefined,
                          }}
                        >
                          {isPosted ? <CheckCircle2 size={12} /> : null} {isPosted ? `Đã đăng ${chLabel}` : chLabel}
                        </button>
                      );
                    })}
                    <input
                      className="input"
                      style={{ flex: 1, minWidth: 170, minHeight: 28, padding: '3px 9px', fontSize: 11.8 }}
                      placeholder="Ghi chú link bài đăng / giờ hẹn đăng..."
                      value={pubNoteDraft}
                      onChange={(e) => setPubNoteDraft(e.target.value)}
                      onBlur={() => {
                        if (pubNoteDraft.trim() !== (detail.published_note || '').trim()) {
                          handleSavePublishNote();
                        }
                      }}
                      onKeyDown={(e) => e.key === 'Enter' && handleSavePublishNote()}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
                  {completedClips.length > 0 && (
                    <>
                      <a
                        href={studioApi.getProjectZipUrl(detail.id)}
                        download={`ChaosShortVideo_${detail.id}.zip`}
                        className="btn btn-primary btn-sm"
                        style={{ textDecoration: 'none' }}
                        title="Tải trọn gói 1 tệp .ZIP gồm toàn bộ Video MP4, Ảnh bìa & Nội dung SEO"
                      >
                        <Archive size={14} /> Tải trọn gói (.ZIP)
                      </a>
                      <a
                        href={studioApi.getProjectCapcutPackUrl(detail.id)}
                        download={`CapCut_StemPack_${detail.id}.zip`}
                        className="btn btn-secondary btn-sm"
                        style={{ textDecoration: 'none', borderColor: 'var(--brand-border)' }}
                        title="Tải Gói Tách Lớp cho CapCut PC (Voice sạch không nhạc nền .wav + Phụ đề .srt + Thẻ PNG trong suốt)"
                      >
                        <Columns size={14} /> Gói Tách Lớp CapCut (.ZIP)
                      </a>
                    </>
                  )}

                  {canQuickEdit && detail.state !== 'AWAITING_REVIEW' && (
                    <button
                      type="button"
                      className={`btn btn-sm ${quickEditOpen ? 'btn-primary' : 'btn-secondary'}`}
                      disabled={busyAction}
                      onClick={handleOpenQuickReEdit}
                    >
                      <Edit3 size={14} />{' '}
                      {quickEditOpen ? 'Đóng khung chỉnh sửa' : 'Chỉnh sửa & Xuất lại nhanh'}
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

              {/* REAL-TIME TELEMETRY PROGRESS BAR + STREAMING CONSOLE LOG TERMINAL */}
              {(isRunning ||
                isPaused ||
                isInterruptedFromOldSession ||
                detail.state === 'QUEUED' ||
                (liveProgress?.logs?.length > 0 && detail.state === 'FAILED')) && (() => {
                const consoleLogs = Array.isArray(liveProgress?.logs) ? liveProgress.logs : [];
                const curStage = liveProgress?.stage || detail.state;
                const pipelinePhases = [
                  { key: 'PREP', label: '1. Kịch bản & Nguồn', match: ['INGESTING', 'TRANSCRIBING_GPU', 'AI_ANALYZING'] },
                  { key: 'AUDIO', label: '2. Thu giọng & Trộn âm', match: ['GENERATING_AUDIO', 'GENERATING_ASSETS'] },
                  { key: 'VISUAL', label: '3. Vẽ thẻ / Hình ảnh', match: ['GENERATING_VISUALS'] },
                  { key: 'COMP', label: '4. Dựng khung 9:16', match: ['ASSEMBLING_FRAMES'] },
                  { key: 'MUX', label: '5. Xuất MP4 & SEO', match: ['RENDERING_NVENC', 'PACKAGING_SEO'] },
                ];
                const activePhaseIdx = Math.max(
                  0,
                  pipelinePhases.findIndex((ph) => ph.match.includes(curStage))
                );
                const stageBadgeMeta = (st) => {
                  if (st === 'INGESTING' || st === 'TRANSCRIBING_GPU') return ['NGUỒN', '#38bdf8'];
                  if (st === 'AI_ANALYZING') return ['AI BRAIN', '#a78bfa'];
                  if (st === 'GENERATING_AUDIO' || st === 'GENERATING_ASSETS') return ['TTS AUDIO', '#34d399'];
                  if (st === 'GENERATING_VISUALS') return ['VISUAL', '#fbbf24'];
                  if (st === 'ASSEMBLING_FRAMES') return ['9:16 FPS', '#f472b6'];
                  if (st === 'RENDERING_NVENC') return ['NVENC MP4', '#22d3ee'];
                  if (st === 'PACKAGING_SEO') return ['SEO PACK', '#fde047'];
                  if (st === 'COMPLETED') return ['HOÀN TẤT', '#4ade80'];
                  if (st === 'FAILED' || st === 'CANCELLED') return ['DỪNG/LỖI', '#f87171'];
                  return [st || 'STUDIO', '#94a3b8'];
                };

                return (
                  <div className="step-box" style={{ marginBottom: 16 }}>
                    {/* 5-Stage Visual Pipeline Stepper */}
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(125px, 1fr))',
                        gap: 6,
                        marginBottom: 10,
                      }}
                    >
                      {pipelinePhases.map((ph, pIdx) => {
                        const isDonePhase = !isInterruptedFromOldSession && pIdx < activePhaseIdx;
                        const isCurPhase = !isInterruptedFromOldSession && pIdx === activePhaseIdx && detail.state !== 'QUEUED';
                        return (
                          <div
                            key={ph.key}
                            style={{
                              padding: '5px 8px',
                              borderRadius: 7,
                              fontSize: 11.4,
                              fontWeight: isCurPhase ? 700 : 600,
                              display: 'flex',
                              alignItems: 'center',
                              gap: 5,
                              border: isCurPhase
                                ? '1px solid var(--brand)'
                                : isDonePhase
                                ? '1px solid rgba(16, 185, 129, 0.45)'
                                : '1px solid var(--border-subtle)',
                              background: isCurPhase
                                ? 'var(--brand-soft)'
                                : isDonePhase
                                ? 'rgba(16, 185, 129, 0.10)'
                                : 'var(--bg-elevated)',
                              color: isCurPhase
                                ? 'var(--brand-text)'
                                : isDonePhase
                                ? 'var(--success-text)'
                                : 'var(--text-muted)',
                            }}
                          >
                            {isDonePhase ? (
                              <CheckCircle2 size={12} />
                            ) : isCurPhase && isRunning ? (
                              <Loader2 size={12} className="spin" />
                            ) : (
                              <Clock size={11} />
                            )}
                            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {ph.label}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 10,
                        flexWrap: 'wrap',
                        marginBottom: 7,
                      }}
                    >
                      <div
                        style={{
                          fontSize: 13.6,
                          fontWeight: 700,
                          color: 'var(--text-primary)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 7,
                          minWidth: 0,
                          flex: 1,
                        }}
                      >
                        {isRunning && <Loader2 size={15} className="spin" style={{ color: 'var(--brand)', flexShrink: 0 }} />}
                        <span style={{ wordBreak: 'break-word' }}>
                          {isInterruptedFromOldSession
                            ? 'Dự án tạm dừng từ phiên trước — bấm nút Tiếp tục để xuất nốt các phần còn thiếu.'
                            : liveProgress?.message || STAGE_LABELS[detail.state]}
                        </span>
                      </div>
                      <div
                        className="text-sub"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 11,
                          fontSize: 12.5,
                          flexWrap: 'wrap',
                        }}
                      >
                        {liveProgress?.step_label && (
                          <span className="badge badge-info">{liveProgress.step_label}</span>
                        )}
                        <LiveElapsedReadout
                          baseElapsedSec={liveProgress?.elapsed_sec || 0}
                          baseEtaSec={liveProgress?.eta_sec ?? null}
                          anchorRef={progressAnchorMonoRef}
                          isRunning={isRunning}
                        />
                        <strong style={{ color: 'var(--brand-text)', fontSize: 14 }}>
                          {Number(pctVal).toFixed(1)}%
                        </strong>
                      </div>
                    </div>

                    <div className="progress-track" style={{ height: 11, marginBottom: 11 }}>
                      <div
                        className={`progress-fill ${isPaused ? 'paused' : isRunning ? 'is-live-shimmer' : ''}`}
                        style={{ width: `${Math.max(2.5, pctVal)}%` }}
                      />
                    </div>

                    {/* LIVE STREAMING CONSOLE LOG VIEWER */}
                    <div className="live-console-terminal">
                      <div className="live-console-header">
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span className="console-traffic-dots">
                            <i style={{ background: '#ef4444' }} />
                            <i style={{ background: '#f59e0b' }} />
                            <i style={{ background: '#22c55e' }} />
                          </span>
                          <Terminal size={13} style={{ color: '#38bdf8' }} />
                          <span style={{ fontWeight: 700, color: '#e2e8f0', fontSize: 11.8 }}>
                            NHẬT KÝ CHẠY THỰC TẾ (LIVE CONSOLE)
                          </span>
                          {isRunning && (
                            <span className="console-live-pill">
                              <span className="console-live-dot" /> Đang xử lý trực tiếp
                            </span>
                          )}
                        </div>
                        <button
                          type="button"
                          onClick={() => setConsoleExpanded((p) => !p)}
                          style={{
                            background: 'rgba(148, 163, 184, 0.14)',
                            border: '1px solid rgba(148, 163, 184, 0.28)',
                            color: '#cbd5e1',
                            borderRadius: 5,
                            padding: '2px 8px',
                            fontSize: 11,
                            cursor: 'pointer',
                          }}
                        >
                          {consoleExpanded
                            ? `Thu gọn (${consoleLogs.length} dòng)`
                            : `Mở rộng Console (${consoleLogs.length} dòng)`}
                        </button>
                      </div>

                      {consoleExpanded && (
                        <div className="live-console-body" ref={consoleBodyRef}>
                          {consoleLogs.length === 0 ? (
                            <div className="console-log-row">
                              <span className="console-ts">[{new Date().toLocaleTimeString('vi-VN', { hour12: false })}]</span>
                              <span className="console-tag" style={{ color: '#38bdf8' }}>[INIT]</span>
                              <span className="console-msg">
                                {isInterruptedFromOldSession
                                  ? 'Phiên làm việc trước đã dừng — sẵn sàng nhận lệnh Tiếp tục từ bạn.'
                                  : liveProgress?.message || 'Đang kết nối luồng nhật ký thực thi từ máy chủ...'}
                                {isRunning && <span className="console-cursor-blink">▋</span>}
                              </span>
                            </div>
                          ) : (
                            consoleLogs.map((entry, lIdx) => {
                              const [tagLbl, tagColor] = stageBadgeMeta(entry.stage);
                              const isLastLine = lIdx === consoleLogs.length - 1;
                              return (
                                <div key={entry.seq || lIdx} className="console-log-row">
                                  <span className="console-ts">[{entry.ts || '--:--:--'}]</span>
                                  <span className="console-tag" style={{ color: tagColor }}>
                                    [{tagLbl}]
                                  </span>
                                  <span className="console-pct">{Number(entry.percent ?? 0).toFixed(1)}%</span>
                                  <span className="console-msg">
                                    {entry.text}
                                    {isLastLine && isRunning && (
                                      <span className="console-cursor-blink">▋</span>
                                    )}
                                  </span>
                                </div>
                              );
                            })
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()}

              {detail.state === 'FAILED' && (
                <div
                  style={{
                    padding: '12px 14px',
                    borderRadius: 9,
                    background: 'rgba(239, 68, 68, 0.12)',
                    border: '1px solid rgba(239, 68, 68, 0.42)',
                    color: 'var(--danger)',
                    fontWeight: 600,
                    marginBottom: 16,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <AlertCircle size={17} />
                  <span>Chi tiết lỗi: {detail.error_message}</span>
                </div>
              )}

              {/* REVIEW & QUICK RE-EDIT STUDIO (WITH REAL-TIME LINE DURATION ~X.Xs & STICKY EXPORT BAR) */}
              {(detail.state === 'AWAITING_REVIEW' || quickEditOpen) &&
                editableClips.length > 0 && (
                  <div style={{ marginBottom: completedClips.length > 0 ? 18 : 0 }}>
                    <div className="step-box" style={{ borderColor: 'var(--brand)' }}>
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: 12,
                          paddingBottom: 10,
                          borderBottom: '1px solid var(--border)',
                          flexWrap: 'wrap',
                          gap: 8,
                        }}
                      >
                        <strong style={{ fontSize: 14.5, color: 'var(--brand-text)' }}>
                          Biên tập kịch bản, ước lượng giây đọc từng câu, đổi giọng &amp; xuất lại nhanh
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

                      <div className="form-grid" style={{ marginBottom: 12 }}>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label">Chuyển cảnh mượt chuẩn CapCut</label>
                          <select
                            className="select"
                            value={layoutConfig.transition_style || 'CAPCUT_DISSOLVE'}
                            onChange={(e) =>
                              updateQuickLayout({ transition_style: e.target.value })
                            }
                          >
                            <option value="CAPCUT_DISSOLVE">
                              Mờ chồng êm ái (Mượt chuẩn CapCut)
                            </option>
                            <option value="CAPCUT_SMOOTH_SLIDE">
                              Lướt ngang mượt mà (Smooth Slide)
                            </option>
                            <option value="CAPCUT_ZOOM_FLOW">Thu phóng mềm mại (Zoom Flow)</option>
                            <option value="CAPCUT_FLASH_BEAT">Chớp sáng tinh tế (Soft Flash)</option>
                            <option value="STATIC_LOOKBOOK">
                              Đứng tĩnh 100% (Không zoom, không rung)
                            </option>
                          </select>
                        </div>

                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label">Kiểu nền &amp; tỷ lệ khung hình xuất</label>
                          <div style={{ display: 'flex', gap: 8 }}>
                            {detail.mode === 'PRODUCT_SHOWCASE' && (
                              <select
                                className="select"
                                style={{ flex: 1 }}
                                value={layoutConfig.product_framing || 'BLURRED_STUDIO_CARD'}
                                onChange={(e) =>
                                  updateQuickLayout({ product_framing: e.target.value })
                                }
                              >
                                <option value="BLURRED_STUDIO_CARD">Thẻ nguyên vẹn + Nền mờ</option>
                                <option value="VELVET_DARK_LUXURY">
                                  Thẻ nguyên vẹn + Nền Đen Nhung
                                </option>
                                <option value="FULL_BLEED_LUXURY">Phóng vừa tràn khung</option>
                              </select>
                            )}
                            <select
                              className="select"
                              style={{ width: detail.mode === 'PRODUCT_SHOWCASE' ? 132 : '100%' }}
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

                      <div className="toggle-grid" style={{ marginBottom: 14 }}>
                        <SwitchCard
                          checked={layoutConfig.show_top_banner !== false}
                          onChange={(val) => updateQuickLayout({ show_top_banner: val })}
                        >
                          Hiện tiêu đề đầu
                        </SwitchCard>
                        {detail.mode === 'PRODUCT_SHOWCASE' && (
                          <>
                            <SwitchCard
                              checked={Boolean(layoutConfig.sales_badge_enabled)}
                              onChange={(val) => updateQuickLayout({ sales_badge_enabled: val })}
                            >
                              Hiện nhãn giá/địa chỉ
                            </SwitchCard>
                            <SwitchCard
                              icon={Wand2}
                              checked={Boolean(layoutConfig.studio_cutout_enabled)}
                              onChange={(val) => updateQuickLayout({ studio_cutout_enabled: val })}
                            >
                              Tách nền Studio
                            </SwitchCard>
                            <SwitchCard
                              icon={Columns}
                              checked={Boolean(layoutConfig.comparison_split_enabled)}
                              onChange={(val) =>
                                updateQuickLayout({ comparison_split_enabled: val })
                              }
                            >
                              Chia đôi so sánh A/B
                            </SwitchCard>
                          </>
                        )}
                        <SwitchCard
                          checked={Boolean(layoutConfig.outro_card_enabled)}
                          onChange={(val) => updateQuickLayout({ outro_card_enabled: val })}
                        >
                          Thẻ kết 2.5s cuối
                        </SwitchCard>
                      </div>

                      <div className="form-grid" style={{ marginBottom: 12 }}>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label">Kiểu Ảnh Bìa TikTok / Shorts</label>
                          <select
                            className="select"
                            value={layoutConfig.cover_style || 'CLEAN_POSTER'}
                            onChange={(e) => updateQuickLayout({ cover_style: e.target.value })}
                          >
                            <option value="CLEAN_POSTER">Bìa sạch tự nhiên</option>
                            <option value="BOLD_HOOK">
                              Chữ lớn nổi bật trên lưới 3 cột TikTok
                            </option>
                            <option value="LUXURY_MAGAZINE">
                              Khung tạp chí Đen Nhung &amp; Vàng Champagne
                            </option>
                          </select>
                        </div>
                        <div className="form-group" style={{ marginBottom: 0 }}>
                          <label className="form-label">Tiêu đề lớn trên Ảnh Bìa (tùy chọn)</label>
                          <input
                            className="input"
                            placeholder="VD: Test Âm Thực Tế • Gỗ Thịt Nguyên Tấm"
                            value={layoutConfig.cover_headline || ''}
                            onChange={(e) => updateQuickLayout({ cover_headline: e.target.value })}
                          />
                        </div>
                      </div>

                      {detail.mode === 'PRODUCT_SHOWCASE' && editablePhotoList.length > 1 && (
                        <div style={{ marginBottom: 14 }}>
                          <div className="form-label">
                            Thứ tự trình chiếu ({editablePhotoList.length} mục — lên hình đủ 100%):
                          </div>
                          <div
                            style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}
                          >
                            {editablePhotoList.map((ph, pIdx) => (
                              <div
                                key={`${ph.local_path}_${pIdx}`}
                                style={{
                                  width: 82,
                                  flexShrink: 0,
                                  background: 'var(--bg-panel)',
                                  border: '1px solid var(--border)',
                                  borderRadius: 8,
                                  padding: 5,
                                  textAlign: 'center',
                                }}
                              >
                                {ph.isVideo ? (
                                  <video
                                    src={ph.media_url}
                                    muted
                                    style={{
                                      width: '100%',
                                      height: 70,
                                      objectFit: 'contain',
                                      background: '#08090c',
                                      borderRadius: 4,
                                    }}
                                  />
                                ) : (
                                  <img
                                    src={ph.media_url}
                                    alt={`Mục ${pIdx + 1}`}
                                    style={{
                                      width: '100%',
                                      height: 70,
                                      objectFit: 'contain',
                                      background: '#08090c',
                                      borderRadius: 4,
                                    }}
                                  />
                                )}
                                <div
                                  className="text-sub"
                                  style={{ fontSize: 11, fontWeight: 600, margin: '3px 0' }}
                                >
                                  {ph.isVideo ? `Clip ${pIdx + 1}` : `Ảnh ${pIdx + 1}`}
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'center', gap: 4 }}>
                                  <button
                                    type="button"
                                    className="btn btn-secondary btn-sm"
                                    style={{ padding: '1px 5px', minHeight: 22 }}
                                    disabled={pIdx === 0}
                                    onClick={() => moveEditablePhoto(pIdx, pIdx - 1)}
                                  >
                                    <ArrowLeft size={11} />
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-secondary btn-sm"
                                    style={{ padding: '1px 5px', minHeight: 22 }}
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

                      <div className="form-grid" style={{ marginBottom: 14 }}>
                        <div className="selector-card">
                          <label className="form-label" style={{ marginBottom: 0 }}>
                            Hình thức âm thanh &amp; phụ đề khi xuất
                          </label>
                          <select
                            className="select"
                            value={reviewAudioSubMode}
                            onChange={(e) => setReviewAudioSubMode(e.target.value)}
                          >
                            <option value="VIET_DUB_AND_SUB">Lồng tiếng + Phụ đề Việt</option>
                            <option value="VIET_DUB_NO_SUB">
                              Chỉ Lồng tiếng Việt (Tắt chữ phụ đề)
                            </option>
                            <option value="VIET_SUB_KEEP_ORIG">
                              Chỉ ghép Phụ đề Việt (Giữ tiếng gốc)
                            </option>
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
                        <div>
                          <InlineVoiceSelector
                            voices={voices}
                            voiceId={selectedVoice}
                            onChange={setSelectedVoice}
                            voiceSpeed={globalVoiceSpeed}
                            onSpeedChange={setGlobalVoiceSpeed}
                            voicePitch={globalVoicePitch}
                            onPitchChange={setGlobalVoicePitch}
                            defaultCategory={
                              detail.mode === 'MOVIE_CLIPPER'
                                ? 'MOVIE_DUB'
                                : detail.mode === 'PRODUCT_SHOWCASE'
                                ? 'ECOMMERCE_SALES'
                                : 'ALL'
                            }
                            notify={notify}
                          />
                        </div>
                      )}
                    </div>

                    {editableClips.map((clip, cIdx) => {
                      const isChecked = selectedParts.includes(clip.part_number);
                      const clipEstTotalSec = clip.lines.reduce((acc, ln) => {
                        if (ln.is_real_demo_slot) return acc + 6;
                        const spd = ln.voice_speed_override ?? globalVoiceSpeed;
                        return acc + estimateSpokenSeconds(ln.vi_text, spd);
                      }, 0);

                      return (
                        <div
                          key={clip.clip_id}
                          className="step-box"
                          style={{
                            borderColor: isChecked ? 'var(--brand)' : 'var(--border)',
                            opacity: isChecked ? 1 : 0.68,
                          }}
                        >
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              flexWrap: 'wrap',
                              gap: 8,
                              marginBottom: 10,
                            }}
                          >
                            <label
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                fontWeight: 700,
                                color: 'var(--text-primary)',
                                cursor: 'pointer',
                              }}
                            >
                              <input
                                type="checkbox"
                                style={{ width: 16, height: 16, accentColor: 'var(--brand)' }}
                                checked={isChecked}
                                onChange={() => togglePart(clip.part_number)}
                              />
                              Phần {clip.part_number} ({Math.round(clip.source_start_ms / 1000)}s –{' '}
                              {Math.round(clip.source_end_ms / 1000)}s)
                            </label>
                            <span className="badge badge-info" style={{ fontSize: 11.5 }}>
                              <Clock size={12} /> {clip.lines.length} câu • Ước tính đọc ~
                              {Math.round(clipEstTotalSec)}s
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

                          <div style={{ display: 'grid', gap: 8, maxHeight: 360, overflowY: 'auto' }}>
                            {clip.lines.map((ln, lIdx) => {
                              const lKey = `${cIdx}_${lIdx}`;
                              const isPlayingThis = previewingLineKey === lKey;
                              const effLineSpd = ln.voice_speed_override ?? globalVoiceSpeed;
                              const estSec = estimateSpokenSeconds(ln.vi_text, effLineSpd);

                              return (
                                <div
                                  key={ln.seq_index}
                                  style={{
                                    display: 'flex',
                                    gap: 7,
                                    alignItems: 'center',
                                    flexWrap: 'wrap',
                                    padding: '7px 10px',
                                    borderRadius: 8,
                                    background: 'var(--bg-panel)',
                                    border: '1px solid var(--border)',
                                  }}
                                >
                                  <span
                                    className="text-sub"
                                    style={{ fontSize: 11.8, minWidth: 44, fontWeight: 700 }}
                                  >
                                    Câu {lIdx + 1}
                                  </span>

                                  {detail.mode === 'PRODUCT_SHOWCASE' &&
                                    (ln.is_real_demo_slot ? (
                                      <span className="badge badge-ok">Tiếng đàn / Clip mộc</span>
                                    ) : (
                                      detail.product_image_urls?.length > 0 && (
                                        <select
                                          className="select"
                                          style={{
                                            width: 96,
                                            minHeight: 34,
                                            padding: '4px 8px',
                                            fontSize: 12.2,
                                          }}
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

                                  {detail.mode === 'THREADS_TOPIC' && (
                                    <>
                                      <span className="badge badge-info" style={{ fontSize: 11 }}>
                                        {ln.is_op_post ? 'OP' : ln.speaker_handle || `#${lIdx}`}
                                      </span>
                                      <select
                                        className="select"
                                        style={{
                                          width: 145,
                                          minHeight: 34,
                                          padding: '4px 7px',
                                          fontSize: 12,
                                        }}
                                        value={ln.voice_profile_override || selectedVoice}
                                        onChange={(e) =>
                                          handleLinePatch(cIdx, lIdx, {
                                            voice_profile_override: e.target.value,
                                          })
                                        }
                                        title="Giọng đọc riêng của bình luận này"
                                      >
                                        {voices.map((v) => (
                                          <option key={v.profile_id} value={v.profile_id}>
                                            {v.display_name.split('—')[0].trim()}
                                          </option>
                                        ))}
                                      </select>
                                    </>
                                  )}

                                  {detail.mode === 'TOPIC_VIDEO' &&
                                    (ln.image_prompt?.startsWith('LOCAL_IMAGE:') ? (
                                      <span
                                        className="badge badge-ok"
                                        style={{ cursor: 'pointer' }}
                                        title="Bấm để bỏ ảnh riêng và cho AI tự vẽ lại theo câu này"
                                        onClick={() =>
                                          handleLinePatch(cIdx, lIdx, { image_prompt: '' })
                                        }
                                      >
                                        Ảnh riêng ×
                                      </span>
                                    ) : (
                                      <label
                                        className="btn btn-secondary btn-sm"
                                        style={{
                                          padding: '0 8px',
                                          minHeight: 34,
                                          cursor: 'pointer',
                                        }}
                                        title="Mặc định AI tự vẽ cảnh khớp câu này • Bấm nếu muốn tải ảnh riêng"
                                      >
                                        <ImagePlus size={13} />
                                        <input
                                          type="file"
                                          accept="image/*"
                                          hidden
                                          onChange={async (ev) => {
                                            const f = ev.target.files?.[0];
                                            ev.target.value = '';
                                            if (!f) return;
                                            try {
                                              const up = await studioApi.uploadStudioFile(
                                                f,
                                                'topic_scene'
                                              );
                                              handleLinePatch(cIdx, lIdx, {
                                                image_prompt: `LOCAL_IMAGE:${up.local_path}`,
                                              });
                                              notify(`Đã gắn ảnh riêng cho Câu ${lIdx + 1}.`);
                                            } catch (err) {
                                              notify(`Lỗi tải ảnh cảnh: ${err.message}`);
                                            }
                                          }}
                                        />
                                      </label>
                                    ))}

                                  <input
                                    className="input"
                                    style={{
                                      flex: 1,
                                      minWidth: 195,
                                      minHeight: 34,
                                      padding: '5px 10px',
                                    }}
                                    value={ln.vi_text}
                                    onChange={(e) =>
                                      handleLinePatch(cIdx, lIdx, {
                                        vi_text: e.target.value,
                                        ...(detail.mode === 'TOPIC_VIDEO' &&
                                        !ln.image_prompt?.startsWith('LOCAL_IMAGE:')
                                          ? { image_prompt: '', stock_keywords: [] }
                                          : {}),
                                      })
                                    }
                                  />

                                  {!ln.is_real_demo_slot && (
                                    <>
                                      <span
                                        className="badge"
                                        style={{
                                          fontSize: 11,
                                          padding: '2px 7px',
                                          minWidth: 50,
                                          justifyContent: 'center',
                                        }}
                                        title="Thời lượng giọng đọc ước tính cho câu này"
                                      >
                                        ~{estSec.toFixed(1)}s
                                      </span>

                                      <select
                                        className="select"
                                        title="Tốc độ đọc riêng cho câu này"
                                        style={{
                                          width: 100,
                                          minHeight: 34,
                                          padding: '4px 7px',
                                          fontSize: 12,
                                        }}
                                        value={
                                          ln.voice_speed_override === null
                                            ? ''
                                            : String(ln.voice_speed_override)
                                        }
                                        onChange={(e) =>
                                          handleLinePatch(cIdx, lIdx, {
                                            voice_speed_override:
                                              e.target.value === ''
                                                ? null
                                                : parseFloat(e.target.value),
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
                                        style={{
                                          width: 104,
                                          minHeight: 34,
                                          padding: '4px 7px',
                                          fontSize: 12,
                                        }}
                                        value={
                                          ln.voice_pitch_override === null
                                            ? ''
                                            : String(ln.voice_pitch_override)
                                        }
                                        onChange={(e) =>
                                          handleLinePatch(cIdx, lIdx, {
                                            voice_pitch_override:
                                              e.target.value === ''
                                                ? null
                                                : parseFloat(e.target.value),
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
                                        className={`btn btn-sm ${
                                          isPlayingThis ? 'btn-primary' : 'btn-secondary'
                                        }`}
                                        style={{ padding: '0 9px', minHeight: 34 }}
                                        title="Nghe thử riêng câu này"
                                        onClick={() => handlePreviewSingleLine(cIdx, lIdx, ln)}
                                      >
                                        {isPlayingThis ? (
                                          <Loader2 size={13} />
                                        ) : (
                                          <Volume2 size={13} />
                                        )}
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

                    {/* STICKY QUICK RE-EXPORT ACTION BAR */}
                    <div className="sticky-action-bar" style={{ marginBottom: 4 }}>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
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
                        <span className="text-sub" style={{ fontSize: 12.2 }}>
                          Đã chọn <strong>{selectedParts.length}/{editableClips.length}</strong> phần
                        </span>
                      </div>

                      <button
                        className="btn btn-success"
                        style={{ minHeight: 42, fontWeight: 700 }}
                        disabled={busyAction}
                        onClick={handleApproveAndRender}
                      >
                        <RefreshCw size={15} className={busyAction ? 'spin' : ''} />{' '}
                        {busyAction
                          ? 'Đang khởi chạy xuất video...'
                          : detail.state === 'COMPLETED'
                          ? 'Xuất lại video với chỉnh sửa mới'
                          : `Xuất ${selectedParts.length}/${editableClips.length} phần đã chọn`}
                      </button>
                    </div>
                  </div>
                )}

              {/* COMPLETED MULTIMEDIA PLAYERS & SEO */}
              {completedClips.length > 0 && (
                <div style={{ display: 'grid', gap: 16 }}>
                  {completedClips.map((clip) => {
                    let ytTags = [];
                    let ttTags = [];
                    try {
                      ytTags = JSON.parse(clip.seo?.yt_shorts_tags_json || '[]');
                      ttTags = JSON.parse(clip.seo?.tiktok_hashtags_json || '[]');
                    } catch {
                      // ignore
                    }
                    const tiktokFull = `${clip.seo?.tiktok_caption || ''}\n${ttTags.join(
                      ' '
                    )}`.trim();

                    return (
                      <div key={clip.clip_id} className="result-clip-grid">
                        <div>
                          {clip.video_url && (
                            <video
                              controls
                              playsInline
                              src={`${clip.video_url}?t=${encodeURIComponent(
                                detail.updated_at || ''
                              )}`}
                              poster={clip.cover_url || undefined}
                              style={{
                                width: '100%',
                                borderRadius: 10,
                                border: '1.5px solid var(--border-strong)',
                                aspectRatio: videoCssAspect,
                                background: '#000',
                              }}
                            />
                          )}
                          <div style={{ display: 'grid', gap: 7, marginTop: 9 }}>
                            {clip.video_url && (
                              <a
                                href={clip.video_url}
                                download={`ChaosShortVideo_Part_${clip.part_number}.mp4`}
                                className="btn btn-primary btn-sm"
                                style={{ width: '100%', textDecoration: 'none' }}
                              >
                                <Download size={14} /> Tải Video (.mp4)
                              </a>
                            )}
                            {clip.cover_url && (
                              <a
                                href={clip.cover_url}
                                download={`ChaosShortVideo_Cover_${clip.part_number}.jpg`}
                                className="btn btn-secondary btn-sm"
                                style={{ width: '100%', textDecoration: 'none' }}
                              >
                                <Download size={14} /> Tải Ảnh Bìa (.jpg)
                              </a>
                            )}
                          </div>
                        </div>

                        <div style={{ minWidth: 0 }}>
                          <h4
                            style={{
                              fontSize: 15.5,
                              fontWeight: 700,
                              color: 'var(--text-primary)',
                              marginBottom: 4,
                            }}
                          >
                            Phần {clip.part_number}: {clip.hook_banner_title}
                          </h4>
                          <div
                            className="text-muted"
                            style={{
                              fontSize: 12,
                              marginBottom: 8,
                              wordBreak: 'break-all',
                            }}
                          >
                            Đường dẫn tệp: <code>{clip.output_mp4_path}</code>
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
                                  <strong style={{ fontSize: 13.2, color: 'var(--text-primary)' }}>
                                    Nội dung đăng YouTube Shorts
                                  </strong>
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
                                      onClick={() =>
                                        copyText(clip.seo.yt_shorts_desc, 'mô tả Shorts')
                                      }
                                    >
                                      <Copy size={13} /> Mô tả
                                    </button>
                                  </div>
                                </div>
                                <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                                  {clip.seo.yt_shorts_title}
                                </div>
                                <div
                                  className="text-sub"
                                  style={{ marginTop: 4, whiteSpace: 'pre-line' }}
                                >
                                  {clip.seo.yt_shorts_desc}
                                </div>
                                {ytTags.length > 0 && (
                                  <div className="text-muted" style={{ marginTop: 6, fontSize: 12 }}>
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
                                    flexWrap: 'wrap',
                                  }}
                                >
                                  <strong style={{ fontSize: 13.2, color: 'var(--text-primary)' }}>
                                    Caption &amp; Hashtag đăng TikTok
                                  </strong>
                                  <button
                                    className="btn btn-primary btn-sm"
                                    onClick={() => copyText(tiktokFull, 'nội dung đăng TikTok')}
                                  >
                                    <Copy size={13} /> Sao chép đăng TikTok
                                  </button>
                                </div>
                                <div className="text-sub" style={{ whiteSpace: 'pre-line' }}>
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
                                      flexWrap: 'wrap',
                                    }}
                                  >
                                    <strong
                                      style={{ fontSize: 13.2, color: 'var(--success-text)' }}
                                    >
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
                                  <div className="text-sub" style={{ whiteSpace: 'pre-line' }}>
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
      </div>
    </div>
  );
}
