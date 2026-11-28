import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import {
  Bell,
  BellOff,
  CheckCircle2,
  Clapperboard,
  Copy,
  Cpu,
  FileText,
  Film,
  FolderKanban,
  Loader2,
  MessageSquareText,
  Mic,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  Pause,
  Play,
  QrCode,
  ShoppingBag,
  SlidersHorizontal,
  Smartphone,
  Sparkles,
  Sun,
  Wifi,
  X,
} from 'lucide-react';
import { studioApi } from './modules/m00_core_contracts/apiClient';
import {
  copyTextSafe,
  DEFAULT_LAYOUT_CONFIG,
  formatSecondsVi,
  STAGE_LABELS,
} from './modules/m00_core_contracts/constants';
import TopicStudioForm from './modules/m03_topic_studio/TopicStudioForm';
import Canvas916Designer from './modules/m06_canvas_916/Canvas916Designer';

function lazyWithAutoReload(importer, chunkKey) {
  return lazy(async () => {
    try {
      const mod = await importer();
      try {
        sessionStorage.removeItem(`chaos_chunk_reload_${chunkKey}`);
      } catch {
        // ignore
      }
      return mod;
    } catch (err) {
      const flag = `chaos_chunk_reload_${chunkKey}`;
      const alreadyReloaded = sessionStorage.getItem(flag);
      if (!alreadyReloaded) {
        sessionStorage.setItem(flag, '1');
        window.location.reload();
        return new Promise(() => {});
      }
      throw err;
    }
  });
}

if (typeof window !== 'undefined') {
  window.addEventListener('vite:preloadError', () => {
    if (!sessionStorage.getItem('chaos_vite_preload_reloaded')) {
      sessionStorage.setItem('chaos_vite_preload_reloaded', '1');
      window.location.reload();
    }
  });
}

const MovieStudioForm = lazyWithAutoReload(
  () => import('./modules/m01_m04_movie_studio/MovieStudioForm'),
  'movie'
);
const VoiceCloneLab = lazyWithAutoReload(
  () => import('./modules/m05_voice_lab/VoiceCloneLab'),
  'voices'
);
const ProjectWorkspaceView = lazyWithAutoReload(
  () => import('./modules/m07_review_and_seo/ProjectWorkspaceView'),
  'workspace'
);
const SettingsModal = lazyWithAutoReload(
  () => import('./modules/m07_review_and_seo/SettingsModal'),
  'settings'
);
const ProductStudioForm = lazyWithAutoReload(
  () => import('./modules/m08_product_studio/ProductStudioForm'),
  'product'
);
const ThreadsStudioForm = lazyWithAutoReload(
  () => import('./modules/m09_threads_studio/ThreadsStudioForm'),
  'threads'
);

const CREATION_TABS = new Set(['topic', 'threads', 'product', 'movie']);

const ACTIVE_STATES = [
  'QUEUED',
  'INGESTING',
  'TRANSCRIBING_GPU',
  'AI_ANALYZING',
  'GENERATING_ASSETS',
  'RENDERING_NVENC',
  'PACKAGING_SEO',
];
const ACTIVE_OR_PAUSED = [...ACTIVE_STATES, 'PAUSED'];

function playCompletionChime() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const notes = [523.25, 659.25, 783.99];
    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.001, ctx.currentTime + idx * 0.11);
      gain.gain.exponentialRampToValueAtTime(0.085, ctx.currentTime + idx * 0.11 + 0.025);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + idx * 0.11 + 0.34);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + idx * 0.11);
      osc.stop(ctx.currentTime + idx * 0.11 + 0.36);
    });
  } catch {
    // ignore autoplay restriction
  }
}

function fireDesktopNotification(title, body) {
  try {
    if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted') {
      const n = new Notification(title, {
        body,
        silent: false,
      });
      n.onclick = () => {
        window.focus();
        n.close();
      };
    }
  } catch {
    // ignore
  }
}

export default function App() {
  const [activeTab, setActiveTab] = useState('topic');
  const [lastCreationTab, setLastCreationTab] = useState('topic');
  const [visitedTabs, setVisitedTabs] = useState(() => new Set(['topic']));
  const [theme, setTheme] = useState(() => localStorage.getItem('chaos_theme') || 'dark');
  const [showAllSteps, setShowAllSteps] = useState(
    () => localStorage.getItem('chaos_show_all_steps') === 'true'
  );
  const [systemStatus, setSystemStatus] = useState(null);
  const [voices, setVoices] = useState([]);
  const [bgmPresets, setBgmPresets] = useState([]);
  const [projects, setProjects] = useState([]);
  const [projectGroups, setProjectGroups] = useState([]);
  const [activeGroupId, setActiveGroupId] = useState('ALL');
  const [activeProjectId, setActiveProjectId] = useState('');
  const [workspaceEditingMode, setWorkspaceEditingMode] = useState(null);
  const [inspectorManualOverride, setInspectorManualOverride] = useState(null);

  const [layoutConfig, setLayoutConfig] = useState(DEFAULT_LAYOUT_CONFIG);
  const [previewFramesByTab, setPreviewFramesByTab] = useState({
    movie: '',
    product: '',
    topic: '',
    threads: '',
    workspace: '',
  });
  const [showSettings, setShowSettings] = useState(false);
  const [showLanQrModal, setShowLanQrModal] = useState(false);
  const [selectedLanUrl, setSelectedLanUrl] = useState('');
  const [showMobilePreviewDrawer, setShowMobilePreviewDrawer] = useState(false);
  const [toastMsg, setToastMsg] = useState('');
  const [completionAlertOn, setCompletionAlertOn] = useState(
    () => localStorage.getItem('chaos_alert_on') !== 'false'
  );
  const alertOnRef = useRef(completionAlertOn);
  useEffect(() => {
    alertOnRef.current = completionAlertOn;
    localStorage.setItem('chaos_alert_on', String(completionAlertOn));
  }, [completionAlertOn]);

  const prevStatesRef = useRef({});
  const hasRunningRef = useRef(false);
  const toastTimerRef = useRef(null);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('chaos_theme', theme);
  }, [theme]);

  const handleToggleShowAllSteps = (nextVal) => {
    const val = Boolean(nextVal);
    setShowAllSteps(val);
    try {
      localStorage.setItem('chaos_show_all_steps', String(val));
    } catch {
      // ignore
    }
  };

  const notify = (msg) => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMsg(msg);
    toastTimerRef.current = setTimeout(() => setToastMsg(''), 4000);
  };

  const setTabPreviewFrame = (tabKey, url) => {
    setPreviewFramesByTab((prev) => ({ ...prev, [tabKey]: url || '' }));
  };

  const syncProjectsWithCompletionAlert = (pList, isInitial = false) => {
    setProjects(pList);
    const activeJob = pList.find((p) => ACTIVE_STATES.includes(p.state));
    hasRunningRef.current = Boolean(activeJob);
    if (activeJob) {
      const pct = Math.round(Number(activeJob.live_progress?.percent || 0));
      document.title = `⏳ ${pct}% • ${activeJob.name.slice(0, 28)} — ChaosShortVideo`;
    } else if (!document.hidden) {
      document.title = 'ChaosShortVideo Studio';
    }

    const prevMap = prevStatesRef.current;
    if (!isInitial) {
      for (const p of pList) {
        const oldState = prevMap[p.id];
        if (oldState && ACTIVE_STATES.includes(oldState) && p.state === 'COMPLETED') {
          if (alertOnRef.current) {
            playCompletionChime();
            fireDesktopNotification(
              'ChaosShortVideo — Xuất video hoàn tất!',
              `Dự án "${p.name}" đã dựng xong MP4 & gói SEO.`
            );
          }
          if (document.hidden) {
            document.title = `XONG VIDEO: ${p.name.slice(0, 26)}!`;
          }
          notify(`Đã xuất xong video: "${p.name}"!`);
        } else if (oldState && ACTIVE_STATES.includes(oldState) && p.state === 'FAILED') {
          if (alertOnRef.current) {
            fireDesktopNotification(
              'Dự án gặp sự cố khi xử lý',
              `"${p.name}": ${p.error_message || 'Vui lòng mở ứng dụng để xem chi tiết.'}`
            );
          }
        }
      }
    }
    const nextMap = {};
    for (const p of pList) nextMap[p.id] = p.state;
    prevStatesRef.current = nextMap;
  };

  const refreshAllData = async (isInitial = false) => {
    try {
      const [st, vList, pList, bList, gList] = await Promise.all([
        studioApi.getSystemStatus(),
        studioApi.listVoices(),
        studioApi.listProjects(),
        studioApi.listBgmPresets(),
        studioApi.listProjectGroups(),
      ]);
      setSystemStatus(st);
      if (st?.lan_urls?.[0] && !selectedLanUrl) {
        setSelectedLanUrl(st.lan_urls[0]);
      }
      setVoices(vList);
      syncProjectsWithCompletionAlert(pList, isInitial);
      setBgmPresets(bList);
      setProjectGroups(gList);
      if (!activeProjectId && pList.length > 0) {
        setActiveProjectId(pList[0].id);
      }
    } catch {
      // backend starting
    }
  };

  const refreshGroupsAndProjects = async () => {
    try {
      const [pList, gList] = await Promise.all([
        studioApi.listProjects(),
        studioApi.listProjectGroups(),
      ]);
      syncProjectsWithCompletionAlert(pList, false);
      setProjectGroups(gList);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    refreshAllData(true);
    let timerId = null;
    let cancelled = false;

    const scheduleNext = () => {
      if (cancelled) return;
      const delay = hasRunningRef.current
        ? document.hidden
          ? 5500
          : 2600
        : document.hidden
        ? 30000
        : 18000;
      timerId = setTimeout(async () => {
        if (!document.hidden || hasRunningRef.current) {
          try {
            const [st, pList, gList] = await Promise.all([
              studioApi.getSystemStatus(),
              studioApi.listProjects(),
              studioApi.listProjectGroups(),
            ]);
            if (!cancelled) {
              setSystemStatus(st);
              syncProjectsWithCompletionAlert(pList, false);
              setProjectGroups(gList);
            }
          } catch {
            // ignore transient network blip
          }
        }
        scheduleNext();
      }, delay);
    };

    scheduleNext();
    const onVisChange = () => {
      if (!document.hidden) {
        if (!hasRunningRef.current) document.title = 'ChaosShortVideo Studio';
        refreshGroupsAndProjects();
      }
    };
    document.addEventListener('visibilitychange', onVisChange);
    return () => {
      cancelled = true;
      if (timerId) clearTimeout(timerId);
      document.removeEventListener('visibilitychange', onVisChange);
    };
  }, []);

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (showSettings) setShowSettings(false);
        else if (showLanQrModal) setShowLanQrModal(false);
        else if (showMobilePreviewDrawer) setShowMobilePreviewDrawer(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showSettings, showLanQrModal, showMobilePreviewDrawer]);

  const handleTabSwitch = (nextTab) => {
    if (CREATION_TABS.has(nextTab)) {
      setLastCreationTab(nextTab);
    }
    setActiveTab(nextTab);
    setVisitedTabs((prev) => (prev.has(nextTab) ? prev : new Set([...prev, nextTab])));
    setInspectorManualOverride(null);
    if (nextTab === 'workspace') {
      refreshGroupsAndProjects();
    }
  };

  const handleProjectStarted = async (projectId, initialState) => {
    setActiveProjectId(projectId);
    setActiveTab('workspace');
    setVisitedTabs((prev) => (prev.has('workspace') ? prev : new Set([...prev, 'workspace'])));
    setInspectorManualOverride(null);
    await refreshAllData(false);
    if (initialState === 'QUEUED') {
      notify('Đã đưa dự án vào hàng đợi tự động.');
    } else {
      notify('Đã bắt đầu xử lý video.');
    }
  };

  const primaryGpu = systemStatus?.gpus?.[0];
  const lanUrls = systemStatus?.lan_urls || [];
  const activeLanUrl = selectedLanUrl || lanUrls[0] || window.location.origin;
  const runningProjects = projects.filter((p) => ACTIVE_OR_PAUSED.includes(p.state));
  const pinnedJob = runningProjects[0] || null;
  const queuedCount = projects.filter((p) => p.state === 'QUEUED').length;
  const reviewCount = projects.filter((p) => p.state === 'AWAITING_REVIEW').length;
  const completedCount = projects.filter((p) => p.state === 'COMPLETED').length;
  const currentPreviewFrameUrl = previewFramesByTab[activeTab] || '';

  const autoShowInspector =
    CREATION_TABS.has(activeTab) || (activeTab === 'workspace' && Boolean(workspaceEditingMode));
  const showDesktopInspector =
    inspectorManualOverride !== null ? inspectorManualOverride : autoShowInspector;

  const inspectorContextMode =
    activeTab === 'workspace'
      ? workspaceEditingMode === 'MOVIE_CLIPPER'
        ? 'movie'
        : workspaceEditingMode === 'PRODUCT_SHOWCASE'
        ? 'product'
        : workspaceEditingMode === 'THREADS_TOPIC'
        ? 'threads'
        : 'topic'
      : activeTab === 'movie'
      ? 'movie'
      : activeTab === 'threads'
      ? 'threads'
      : activeTab === 'topic'
      ? 'topic'
      : 'product';

  const handleQuickPauseResume = async (job) => {
    try {
      if (job.state === 'PAUSED') {
        await studioApi.resumeProject(job.id);
        notify('Đã tiếp tục dự án.');
      } else {
        await studioApi.pauseProject(job.id);
        notify('Đã tạm dừng dự án.');
      }
      refreshGroupsAndProjects();
    } catch (err) {
      notify(`Lỗi điều khiển: ${err.message}`);
    }
  };

  const navItems = [
    { id: 'topic', label: 'Tạo Từ Chủ Đề', shortLabel: 'Chủ Đề', icon: FileText },
    {
      id: 'threads',
      label: 'Threads & Bình Luận',
      shortLabel: 'Threads',
      icon: MessageSquareText,
    },
    { id: 'product', label: 'Video Bán Hàng', shortLabel: 'Bán Hàng', icon: ShoppingBag },
    { id: 'movie', label: 'Cắt & Dịch Video', shortLabel: 'Cắt Video', icon: Film },
    {
      id: 'workspace',
      label: 'Danh Sách Dự Án',
      shortLabel: 'Dự Án',
      icon: FolderKanban,
      count: projects.length,
    },
    {
      id: 'voices',
      label: 'Phòng Giọng Đọc',
      shortLabel: 'Giọng Đọc',
      icon: Mic,
      count: voices.length,
    },
  ];

  const apiKeyReady = Boolean(
    systemStatus?.keys_configured?.anthropic || systemStatus?.keys_configured?.gemini
  );

  return (
    <div className="app-shell">
      {/* PINNED TOP PRODUCTION HEADER WITH UNIFIED PIPELINE JOURNEY BAR */}
      <header className="studio-header">
        <div className="brand-wrap">
          <div className="brand-mark">
            <Clapperboard size={19} strokeWidth={2.2} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="brand-title">
              ChaosShortVideo
              <span className="brand-version-pill">Studio v3.5</span>
            </div>
            <div className="brand-sub">
              Hệ thống sản xuất Video Ngắn AI • Đồng bộ từ Ý tưởng đến Xuất bản
            </div>
          </div>
        </div>

        {/* GLOBAL CROSS-PAGE PIPELINE JOURNEY BAR */}
        <div className="pipeline-journey-pill" role="navigation" aria-label="Hành trình sản xuất video">
          <button
            type="button"
            className={`journey-step-btn ${CREATION_TABS.has(activeTab) ? 'active' : ''}`}
            onClick={() => handleTabSwitch(lastCreationTab)}
            title="Quay lại xưởng sáng tạo kịch bản & thiết lập video"
          >
            <Sparkles size={13} />
            <span>1. Tạo kịch bản</span>
          </button>
          <span className="journey-arrow">→</span>
          <button
            type="button"
            className={`journey-step-btn ${
              activeTab === 'workspace' && Boolean(pinnedJob) ? 'active' : ''
            }`}
            onClick={() => {
              if (pinnedJob) setActiveProjectId(pinnedJob.id);
              handleTabSwitch('workspace');
            }}
            title="Theo dõi tiến trình kết xuất GPU thời gian thực"
          >
            {pinnedJob ? (
              <>
                <Loader2 size={13} className="spin" style={{ color: 'var(--brand-text)' }} />
                <span>
                  2. Đang dựng ({Math.round(Number(pinnedJob.live_progress?.percent || 0))}%)
                </span>
              </>
            ) : (
              <>
                <Cpu size={13} />
                <span>2. Hàng đợi GPU</span>
              </>
            )}
          </button>
          <span className="journey-arrow">→</span>
          <button
            type="button"
            className={`journey-step-btn ${
              activeTab === 'workspace' && !pinnedJob ? 'active' : ''
            }`}
            onClick={() => handleTabSwitch('workspace')}
            title="Duyệt kịch bản, tải Video MP4 & sao chép bộ SEO"
          >
            <CheckCircle2 size={13} />
            <span>
              3. Duyệt &amp; Tải MP4
              {reviewCount > 0 ? ` (${reviewCount} chờ)` : completedCount > 0 ? ` (${completedCount})` : ''}
            </span>
          </button>
        </div>

        <div className="header-actions">
          <span className={`badge ${primaryGpu ? 'badge-ok' : 'badge-warn'} hide-on-mobile`}>
            <Cpu size={13} />
            {primaryGpu
              ? `${primaryGpu.name.replace('NVIDIA GeForce ', '')} • ${Math.round(
                  primaryGpu.vram_total_mb / 1024
                )}GB${systemStatus?.nvenc_available ? ' NVENC' : ''}`
              : 'CPU Mode'}
          </span>

          {lanUrls.length > 0 && (
            <button
              type="button"
              className="icon-toolbar-btn hide-on-mobile"
              title={`Quét QR kết nối Điện thoại cùng Wi-Fi (${lanUrls[0]})`}
              onClick={() => setShowLanQrModal(true)}
            >
              <QrCode size={16} />
            </button>
          )}

          <button
            type="button"
            className={`icon-toolbar-btn ${showDesktopInspector ? 'active' : ''} hide-on-mobile`}
            onClick={() => setInspectorManualOverride(!showDesktopInspector)}
            title="Đóng / Mở khung mô phỏng 9:16 và phần cứng bên phải"
          >
            {showDesktopInspector ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
          </button>

          <button
            type="button"
            className={`icon-toolbar-btn ${completionAlertOn ? 'active' : ''} hide-on-mobile`}
            onClick={async () => {
              const nextVal = !completionAlertOn;
              setCompletionAlertOn(nextVal);
              if (nextVal) {
                playCompletionChime();
                if (
                  typeof window !== 'undefined' &&
                  'Notification' in window &&
                  Notification.permission === 'default'
                ) {
                  try {
                    await Notification.requestPermission();
                  } catch {
                    // ignore
                  }
                }
                notify('Đã bật chuông báo hoàn tất video.');
              } else {
                notify('Đã tắt chuông báo hoàn tất.');
              }
            }}
            title={completionAlertOn ? 'Đang bật chuông báo hoàn tất' : 'Đang tắt chuông báo'}
          >
            {completionAlertOn ? <Bell size={16} /> : <BellOff size={16} />}
          </button>

          <button
            type="button"
            className="icon-toolbar-btn"
            onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
            title={theme === 'dark' ? 'Chuyển sang giao diện Sáng' : 'Chuyển sang giao diện Tối'}
          >
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>

          <button className="btn btn-secondary btn-sm" onClick={() => setShowSettings(true)}>
            <SlidersHorizontal size={14} />
            <span className="hide-on-mobile">Cài đặt API</span>
          </button>
        </div>
      </header>

      {/* LOCKED 3-PANE INDEPENDENT SCROLL WORKSPACE */}
      <div className={`studio-layout-3col ${showDesktopInspector ? '' : 'inspector-collapsed'}`}>
        {/* LEFT CLEAN SAAS SIDEBAR */}
        <aside className="studio-sidebar">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <nav className="nav-rail">
              <div className="nav-section-label">Xưởng sáng tạo</div>
              {navItems.slice(0, 4).map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    className={`rail-btn ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => handleTabSwitch(item.id)}
                  >
                    <span className="rail-btn-left">
                      <Icon size={17} strokeWidth={1.9} />
                      <span>{item.label}</span>
                    </span>
                  </button>
                );
              })}

              <div className="nav-section-label" style={{ marginTop: 8 }}>
                Quản lý &amp; Thư viện
              </div>
              {navItems.slice(4).map((item) => {
                const Icon = item.icon;
                const badgeCount =
                  item.id === 'workspace' && reviewCount > 0 ? `${reviewCount} duyệt` : item.count;
                return (
                  <button
                    key={item.id}
                    className={`rail-btn ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => handleTabSwitch(item.id)}
                  >
                    <span className="rail-btn-left">
                      <Icon size={17} strokeWidth={1.9} />
                      <span>{item.label}</span>
                    </span>
                    {badgeCount !== undefined && <span className="rail-count">{badgeCount}</span>}
                  </button>
                );
              })}
            </nav>

            {/* QUICK PARENT PROJECT GROUPS NAVIGATION IN SIDEBAR */}
            {projectGroups.length > 0 && (
              <div className="nav-rail hide-on-mobile">
                <div className="nav-section-label">Nhóm Series ({projectGroups.length})</div>
                {projectGroups.slice(0, 6).map((grp) => (
                  <button
                    key={grp.group_id}
                    type="button"
                    className={`rail-btn ${
                      activeTab === 'workspace' && activeGroupId === grp.group_id ? 'active' : ''
                    }`}
                    onClick={() => {
                      setActiveGroupId(grp.group_id);
                      handleTabSwitch('workspace');
                    }}
                  >
                    <span className="rail-btn-left">
                      <span
                        className="group-dot"
                        style={{ background: grp.color_tag || '#6366f1' }}
                      />
                      <span
                        style={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {grp.name}
                      </span>
                    </span>
                    <span className="rail-count">{grp.project_count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* PINNED LIVE PROGRESS WIDGET */}
          {pinnedJob && (
            <div className="pinned-job-box">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 6,
                }}
              >
                <span
                  className="text-xs fw-700 text-brand"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  {pinnedJob.state !== 'PAUSED' && <span className="pulse-dot" />}
                  {pinnedJob.state === 'PAUSED' ? 'Đang tạm dừng' : 'Đang dựng video'}
                </span>
                {queuedCount > 0 && <span className="badge badge-warn">+{queuedCount} chờ</span>}
              </div>

              <div
                className="text-sm fw-600 text-main"
                style={{
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  marginBottom: 3,
                }}
                title={pinnedJob.name}
              >
                {pinnedJob.name}
              </div>

              <div className="text-xs text-sub">
                {pinnedJob.live_progress?.step_label ||
                  STAGE_LABELS[pinnedJob.state] ||
                  pinnedJob.state}
              </div>

              <div className="progress-track">
                <div
                  className={`progress-fill ${
                    pinnedJob.state === 'PAUSED' ? 'paused' : 'is-live-shimmer'
                  }`}
                  style={{
                    width: `${Math.max(2.5, Math.min(100, pinnedJob.live_progress?.percent || 2.5))}%`,
                  }}
                />
              </div>

              <div
                className="text-xs text-sub"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 10,
                }}
              >
                <strong>{Number(pinnedJob.live_progress?.percent || 0).toFixed(1)}%</strong>
                <span className="text-success fw-600">
                  {pinnedJob.live_progress?.eta_sec !== null &&
                  pinnedJob.live_progress?.eta_sec !== undefined
                    ? `Còn ~${formatSecondsVi(pinnedJob.live_progress.eta_sec)}`
                    : `Đã chạy ${formatSecondsVi(pinnedJob.live_progress?.elapsed_sec || 0)}`}
                </span>
              </div>

              <div style={{ display: 'flex', gap: 6 }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{ flex: 1 }}
                  onClick={() => handleQuickPauseResume(pinnedJob)}
                >
                  {pinnedJob.state === 'PAUSED' ? (
                    <>
                      <Play size={13} /> Tiếp tục
                    </>
                  ) : (
                    <>
                      <Pause size={13} /> Tạm dừng
                    </>
                  )}
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    setActiveProjectId(pinnedJob.id);
                    handleTabSwitch('workspace');
                  }}
                >
                  Chi tiết
                </button>
              </div>
            </div>
          )}
        </aside>

        {/* CENTER INDEPENDENT SCROLL WORKSPACE */}
        <main className="studio-center-scroll">
          <div className="studio-center-inner">
            <div style={{ display: activeTab === 'topic' ? 'block' : 'none' }}>
              <TopicStudioForm
                voices={voices}
                bgmPresets={bgmPresets}
                layoutConfig={layoutConfig}
                setLayoutConfig={setLayoutConfig}
                projectGroups={projectGroups}
                onGroupsChanged={refreshGroupsAndProjects}
                onProjectStarted={handleProjectStarted}
                onNavigateTab={handleTabSwitch}
                showAllSteps={showAllSteps}
                onToggleShowAllSteps={handleToggleShowAllSteps}
                notify={notify}
                apiKeyConfigured={apiKeyReady}
                onOpenApiSettings={() => setShowSettings(true)}
              />
            </div>

            <Suspense
              fallback={
                <div className="card text-sm text-sub" style={{ padding: 28 }}>
                  Đang mở không gian làm việc...
                </div>
              }
            >
              {visitedTabs.has('threads') && (
                <div style={{ display: activeTab === 'threads' ? 'block' : 'none' }}>
                  <ThreadsStudioForm
                    voices={voices}
                    bgmPresets={bgmPresets}
                    layoutConfig={layoutConfig}
                    setLayoutConfig={setLayoutConfig}
                    projectGroups={projectGroups}
                    onGroupsChanged={refreshGroupsAndProjects}
                    onPreviewFrameReady={(u) => setTabPreviewFrame('threads', u)}
                    onProjectStarted={handleProjectStarted}
                    onNavigateTab={handleTabSwitch}
                    showAllSteps={showAllSteps}
                    onToggleShowAllSteps={handleToggleShowAllSteps}
                    notify={notify}
                    apiKeyConfigured={apiKeyReady}
                    onOpenApiSettings={() => setShowSettings(true)}
                  />
                </div>
              )}

              {visitedTabs.has('product') && (
                <div style={{ display: activeTab === 'product' ? 'block' : 'none' }}>
                  <ProductStudioForm
                    voices={voices}
                    bgmPresets={bgmPresets}
                    layoutConfig={layoutConfig}
                    setLayoutConfig={setLayoutConfig}
                    projectGroups={projectGroups}
                    onGroupsChanged={refreshGroupsAndProjects}
                    onPreviewFrameReady={(u) => setTabPreviewFrame('product', u)}
                    onProjectStarted={handleProjectStarted}
                    onNavigateTab={handleTabSwitch}
                    showAllSteps={showAllSteps}
                    onToggleShowAllSteps={handleToggleShowAllSteps}
                    notify={notify}
                    apiKeyConfigured={apiKeyReady}
                    onOpenApiSettings={() => setShowSettings(true)}
                  />
                </div>
              )}

              {visitedTabs.has('movie') && (
                <div style={{ display: activeTab === 'movie' ? 'block' : 'none' }}>
                  <MovieStudioForm
                    voices={voices}
                    bgmPresets={bgmPresets}
                    layoutConfig={layoutConfig}
                    setLayoutConfig={setLayoutConfig}
                    projectGroups={projectGroups}
                    onGroupsChanged={refreshGroupsAndProjects}
                    onPreviewFrameReady={(u) => setTabPreviewFrame('movie', u)}
                    onProjectStarted={handleProjectStarted}
                    onNavigateTab={handleTabSwitch}
                    showAllSteps={showAllSteps}
                    onToggleShowAllSteps={handleToggleShowAllSteps}
                    notify={notify}
                  />
                </div>
              )}

              {activeTab === 'voices' && (
                <VoiceCloneLab
                  voices={voices}
                  onVoicesChanged={() => refreshAllData(false)}
                  onBackToStudio={() => handleTabSwitch(lastCreationTab)}
                  notify={notify}
                />
              )}

              {activeTab === 'workspace' && (
                <ProjectWorkspaceView
                  activeProjectId={activeProjectId}
                  projects={projects}
                  projectGroups={projectGroups}
                  activeGroupId={activeGroupId}
                  onSelectGroup={setActiveGroupId}
                  onGroupsChanged={refreshGroupsAndProjects}
                  onSelectProject={setActiveProjectId}
                  onProjectsRefresh={refreshGroupsAndProjects}
                  voices={voices}
                  bgmPresets={bgmPresets}
                  layoutConfig={layoutConfig}
                  setLayoutConfig={setLayoutConfig}
                  onPreviewFrameReady={(u) => setTabPreviewFrame('workspace', u)}
                  onQuickEditStateChange={(isOpen, projMode) =>
                    setWorkspaceEditingMode(isOpen ? projMode : null)
                  }
                  onNavigateTab={handleTabSwitch}
                  lastCreationTab={lastCreationTab}
                  notify={notify}
                />
              )}
            </Suspense>
          </div>
        </main>

        {/* SMART CONTEXT-AWARE RIGHT DESKTOP INSPECTOR */}
        {showDesktopInspector && (
          <div className="right-dock-desktop">
            <Canvas916Designer
              layoutConfig={layoutConfig}
              setLayoutConfig={setLayoutConfig}
              previewFrameUrl={currentPreviewFrameUrl}
              systemStatus={systemStatus}
              onSystemStatusUpdated={setSystemStatus}
              activeTab={activeTab}
              contextMode={inspectorContextMode}
              notify={notify}
            />
          </div>
        )}
      </div>

      {/* FLOATING PREVIEW TRIGGER FOR SMALL SCREENS ONLY */}
      <button
        type="button"
        className="btn btn-primary floating-preview-fab"
        onClick={() => setShowMobilePreviewDrawer(true)}
      >
        <Smartphone size={16} /> Khung 9:16 &amp; GPU
      </button>

      {/* SLIDE-OVER DRAWER FOR SMALL SCREENS */}
      {showMobilePreviewDrawer && (
        <div className="drawer-backdrop" onClick={() => setShowMobilePreviewDrawer(false)}>
          <div className="drawer-sheet" onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 14,
              }}
            >
              <strong className="text-md">Mô phỏng khung 9:16 &amp; Thiết bị</strong>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowMobilePreviewDrawer(false)}
              >
                <X size={15} /> Đóng
              </button>
            </div>
            <Canvas916Designer
              layoutConfig={layoutConfig}
              setLayoutConfig={setLayoutConfig}
              previewFrameUrl={currentPreviewFrameUrl}
              systemStatus={systemStatus}
              onSystemStatusUpdated={setSystemStatus}
              activeTab={activeTab}
              contextMode={inspectorContextMode}
              notify={notify}
            />
          </div>
        </div>
      )}

      {/* MOBILE BOTTOM APP TAB BAR */}
      <nav className="mobile-bottom-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              className={`mobile-nav-item ${activeTab === item.id ? 'active' : ''}`}
              onClick={() => handleTabSwitch(item.id)}
            >
              <Icon size={19} strokeWidth={1.9} />
              <span>{item.shortLabel}</span>
            </button>
          );
        })}
      </nav>

      {/* LAN WI-FI MOBILE QR MODAL */}
      {showLanQrModal && (
        <div className="modal-backdrop" onClick={() => setShowLanQrModal(false)}>
          <div
            className="card"
            onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 460, marginBottom: 0, textAlign: 'center' }}
          >
            <div className="page-header" style={{ marginBottom: 16, textAlign: 'left' }}>
              <div>
                <div className="page-title">
                  <Wifi size={19} /> Kết nối Điện thoại qua Wi-Fi
                </div>
                <div className="page-subtitle">
                  Tải thẳng ảnh &amp; video gốc từ iPhone / Android vào máy chủ qua mạng LAN
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowLanQrModal(false)}
              >
                <X size={15} /> Đóng
              </button>
            </div>

            {lanUrls.length > 1 && (
              <div className="form-group" style={{ textAlign: 'left' }}>
                <label className="form-label">Chọn địa chỉ mạng nội bộ</label>
                <select
                  className="select"
                  value={activeLanUrl}
                  onChange={(e) => setSelectedLanUrl(e.target.value)}
                >
                  {lanUrls.map((u) => (
                    <option key={u} value={u}>
                      {u}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div
              style={{
                display: 'inline-block',
                padding: 14,
                borderRadius: 16,
                background: '#ffffff',
                border: '2px solid var(--brand)',
                marginBottom: 14,
              }}
            >
              <img
                src={studioApi.getLanQrImageUrl(activeLanUrl)}
                alt="LAN Wi-Fi QR Code"
                style={{ width: 210, height: 210, display: 'block' }}
              />
            </div>

            <div className="step-box" style={{ textAlign: 'left', padding: 14, marginBottom: 14 }}>
              <div className="text-sm fw-600" style={{ marginBottom: 4 }}>
                Hướng dẫn kết nối nhanh:
              </div>
              <div className="text-xs text-sub">
                1. Điện thoại kết nối <strong>cùng mạng Wi-Fi</strong> với máy tính này.
                <br />
                2. Mở <strong>Camera điện thoại</strong> quét mã QR trên để mở thẳng giao diện Studio.
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="input fw-600"
                readOnly
                value={activeLanUrl}
                style={{ flex: 1, textAlign: 'center' }}
              />
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  copyTextSafe(activeLanUrl);
                  notify(`Đã sao chép địa chỉ LAN: ${activeLanUrl}`);
                }}
              >
                <Copy size={15} /> Sao chép
              </button>
            </div>
          </div>
        </div>
      )}

      {showSettings && (
        <Suspense fallback={null}>
          <SettingsModal
            systemStatus={systemStatus}
            onClose={() => setShowSettings(false)}
            onUpdated={setSystemStatus}
            onBackupRestored={() => refreshAllData(false)}
            notify={notify}
          />
        </Suspense>
      )}

      {toastMsg && (
        <div
          className={`toast ${
            /^(lỗi|không thể|vui lòng|bắt buộc|có \d+|định dạng|thời lượng|tối đa|khi cấu hình)/i.test(
              toastMsg
            )
              ? 'toast-error'
              : /^đã /i.test(toastMsg)
              ? 'toast-ok'
              : ''
          }`}
        >
          {toastMsg}
        </div>
      )}
    </div>
  );
}
