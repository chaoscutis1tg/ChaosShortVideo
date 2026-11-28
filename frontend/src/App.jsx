import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
import {
  Bell,
  BellOff,
  Clapperboard,
  Copy,
  Cpu,
  FileText,
  Film,
  FolderKanban,
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
  const [visitedTabs, setVisitedTabs] = useState(() => new Set(['topic']));
  const [theme, setTheme] = useState(() => localStorage.getItem('chaos_theme') || 'dark');
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
              '✅ ChaosShortVideo — Xuất video hoàn tất!',
              `Dự án "${p.name}" đã dựng xong MP4 & gói SEO.`
            );
          }
          if (document.hidden) {
            document.title = `✅ XONG VIDEO: ${p.name.slice(0, 26)}!`;
          }
          notify(`Đã xuất xong video: "${p.name}"!`);
        } else if (oldState && ACTIVE_STATES.includes(oldState) && p.state === 'FAILED') {
          if (alertOnRef.current) {
            fireDesktopNotification(
              '⚠️ Dự án gặp sự cố khi xử lý',
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

  // Smart Adaptive Polling: 2.6s ONLY when a job is actively running & tab is visible; 18s when idle!
  useEffect(() => {
    refreshAllData(true);
    let timerId = null;
    let cancelled = false;

    const scheduleNext = () => {
      if (cancelled) return;
      // Keep polling every 5.5s in background tabs WHILE a video is rendering so Chime + Desktop Notification fire on time!
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

  // Global Studio Keyboard Shortcuts (Esc closes modals)
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
  const currentPreviewFrameUrl = previewFramesByTab[activeTab] || '';

  // Smart Context-Aware Inspector: Auto-open on creation tabs or when Quick Re-Edit is open in Workspace;
  // Auto-collapse on Voices Lab and Workspace browsing so 2-column Master-Detail has generous space!
  const autoShowInspector =
    activeTab === 'product' ||
    activeTab === 'movie' ||
    activeTab === 'topic' ||
    activeTab === 'threads' ||
    (activeTab === 'workspace' && Boolean(workspaceEditingMode));
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
      label: 'Giọng Đọc & Thu Mẫu',
      shortLabel: 'Giọng Đọc',
      icon: Mic,
      count: voices.length,
    },
  ];

  return (
    <div className="app-shell">
      {/* PINNED TOP STUDIO HEADER */}
      <header className="studio-header">
        <div className="brand-wrap">
          <div className="brand-mark">
            <Clapperboard size={20} strokeWidth={2.1} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="brand-title">
              ChaosShortVideo
              <span className="brand-version-pill">Studio v3.3</span>
            </div>
            <div className="brand-sub">
              Phân tích ý tưởng bằng AI, dựng video bán hàng, cắt dịch phim & quản lý dự án đa tầng
            </div>
          </div>
        </div>

        <div className="header-actions">
          {lanUrls.length > 0 && (
            <button
              type="button"
              className="badge badge-info hide-on-mobile"
              style={{ cursor: 'pointer' }}
              title="Bấm để mở Mã QR quét bằng điện thoại cùng mạng Wi-Fi"
              onClick={() => setShowLanQrModal(true)}
            >
              <QrCode size={13} /> Điện thoại LAN: {lanUrls[0].replace('http://', '')}
            </button>
          )}

          <span className={`badge ${primaryGpu ? 'badge-ok' : 'badge-warn'} hide-on-mobile`}>
            <Cpu size={13} />{' '}
            {primaryGpu
              ? `${primaryGpu.name} (${Math.round(primaryGpu.vram_total_mb / 1024)}GB${
                  systemStatus?.nvenc_available ? ' • NVENC' : ''
                })`
              : 'Chế độ CPU'}
          </span>

          <button
            type="button"
            className={`btn btn-sm ${showDesktopInspector ? 'btn-primary' : 'btn-secondary'} hide-on-mobile`}
            onClick={() => setInspectorManualOverride(!showDesktopInspector)}
            title="Đóng / Mở bảng mô phỏng khung 9:16 và theo dõi phần cứng bên phải"
          >
            {showDesktopInspector ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
            <span>Khung 9:16 &amp; GPU</span>
          </button>

          <button
            type="button"
            className={`btn btn-sm ${completionAlertOn ? 'btn-primary' : 'btn-secondary'} hide-on-mobile`}
            onClick={async () => {
              const nextVal = !completionAlertOn;
              setCompletionAlertOn(nextVal);
              if (nextVal) {
                playCompletionChime();
                if (typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'default') {
                  try {
                    await Notification.requestPermission();
                  } catch {
                    // ignore
                  }
                }
                notify('Đã bật chuông & thông báo màn hình khi xuất xong video ở tab khác!');
              } else {
                notify('Đã tắt chuông báo hoàn tất.');
              }
            }}
            title="Bật / Tắt chuông báo & thông báo Windows khi render xong lúc bạn đang ở tab khác"
          >
            {completionAlertOn ? <Bell size={14} /> : <BellOff size={14} />}
            <span>{completionAlertOn ? 'Chuông báo' : 'Tắt chuông'}</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
            title="Chuyển đổi giao diện Tối / Sáng dễ nhìn"
          >
            {theme === 'dark' ? (
              <>
                <Sun size={14} /> <span className="hide-on-mobile">Nền sáng</span>
              </>
            ) : (
              <>
                <Moon size={14} /> <span className="hide-on-mobile">Nền tối</span>
              </>
            )}
          </button>

          <button className="btn btn-secondary btn-sm" onClick={() => setShowSettings(true)}>
            <SlidersHorizontal size={14} />{' '}
            <span className="hide-on-mobile">API &amp; Sao lưu</span>
          </button>
        </div>
      </header>

      {/* LOCKED 3-PANE INDEPENDENT SCROLL WORKSPACE */}
      <div className={`studio-layout-3col ${showDesktopInspector ? '' : 'inspector-collapsed'}`}>
        {/* LEFT FIXED SIDEBAR */}
        <aside className="studio-sidebar">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <nav className="nav-rail">
              <div className="nav-section-label">Công cụ sản xuất</div>
              {navItems.slice(0, 4).map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    className={`rail-btn ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => handleTabSwitch(item.id)}
                  >
                    <span className="rail-btn-left">
                      <Icon size={18} strokeWidth={1.9} />
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
                return (
                  <button
                    key={item.id}
                    className={`rail-btn ${activeTab === item.id ? 'active' : ''}`}
                    onClick={() => handleTabSwitch(item.id)}
                  >
                    <span className="rail-btn-left">
                      <Icon size={18} strokeWidth={1.9} />
                      <span>{item.label}</span>
                    </span>
                    {item.count !== undefined && <span className="rail-count">{item.count}</span>}
                  </button>
                );
              })}
            </nav>

            {/* QUICK PARENT PROJECT GROUPS NAVIGATION IN SIDEBAR */}
            {projectGroups.length > 0 && (
              <div className="nav-rail hide-on-mobile" style={{ padding: '10px 10px 12px' }}>
                <div className="nav-section-label" style={{ paddingTop: 2 }}>
                  Dự án cha ({projectGroups.length})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {projectGroups.slice(0, 6).map((grp) => (
                    <button
                      key={grp.group_id}
                      type="button"
                      className={`rail-btn ${
                        activeTab === 'workspace' && activeGroupId === grp.group_id ? 'active' : ''
                      }`}
                      style={{ padding: '7px 10px', fontSize: 12.8 }}
                      onClick={() => {
                        setActiveGroupId(grp.group_id);
                        handleTabSwitch('workspace');
                      }}
                    >
                      <span className="rail-btn-left">
                        <span
                          className="group-dot"
                          style={{ background: grp.color_tag || '#0ea5e9' }}
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
                      <span className="rail-count" style={{ fontSize: 10.8, padding: '1px 6px' }}>
                        {grp.project_count}
                      </span>
                    </button>
                  ))}
                </div>
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
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color: 'var(--brand-text)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  {pinnedJob.state !== 'PAUSED' && <span className="pulse-dot" />}
                  {pinnedJob.state === 'PAUSED' ? 'Đang tạm dừng' : 'Đang xử lý video'}
                </span>
                {queuedCount > 0 && (
                  <span className="badge badge-warn" style={{ fontSize: 10.5, padding: '1px 7px' }}>
                    +{queuedCount} chờ
                  </span>
                )}
              </div>

              <div
                style={{
                  fontSize: 13.5,
                  fontWeight: 700,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  marginBottom: 3,
                }}
                title={pinnedJob.name}
              >
                {pinnedJob.name}
              </div>

              <div className="text-sub" style={{ fontSize: 12 }}>
                {pinnedJob.live_progress?.step_label ||
                  STAGE_LABELS[pinnedJob.state] ||
                  pinnedJob.state}
              </div>

              {pinnedJob.live_progress?.message && (
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: "Consolas, 'JetBrains Mono', monospace",
                    color: 'var(--brand-text)',
                    background: 'rgba(15, 23, 42, 0.55)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 5,
                    padding: '3px 6px',
                    marginTop: 4,
                    marginBottom: 4,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={pinnedJob.live_progress.message}
                >
                  &gt; {pinnedJob.live_progress.message}
                </div>
              )}

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
                className="text-sub"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontSize: 12,
                  marginBottom: 9,
                }}
              >
                <strong>{Number(pinnedJob.live_progress?.percent || 0).toFixed(1)}%</strong>
                <span style={{ color: 'var(--success-text)', fontWeight: 600 }}>
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

        {/* CENTER INDEPENDENT SCROLL WORKSPACE (Lazy-loaded on first visit, then kept mounted!) */}
        <main className="studio-center-scroll">
          <div style={{ display: activeTab === 'topic' ? 'block' : 'none' }}>
            <TopicStudioForm
              voices={voices}
              bgmPresets={bgmPresets}
              layoutConfig={layoutConfig}
              setLayoutConfig={setLayoutConfig}
              projectGroups={projectGroups}
              onGroupsChanged={refreshGroupsAndProjects}
              onProjectStarted={handleProjectStarted}
              notify={notify}
              apiKeyConfigured={Boolean(systemStatus?.keys_configured?.gemini)}
              onOpenApiSettings={() => setShowSettings(true)}
            />
          </div>

          <Suspense
            fallback={
              <div className="card" style={{ padding: 24, fontSize: 13.5 }}>
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
                  notify={notify}
                  apiKeyConfigured={Boolean(systemStatus?.keys_configured?.gemini)}
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
                  notify={notify}
                  apiKeyConfigured={Boolean(systemStatus?.keys_configured?.gemini)}
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
                  notify={notify}
                />
              </div>
            )}

            {activeTab === 'voices' && (
              <VoiceCloneLab
                voices={voices}
                onVoicesChanged={() => refreshAllData(false)}
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
                notify={notify}
              />
            )}
          </Suspense>
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
        <Smartphone size={16} /> Xem trước &amp; Phần cứng
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
                marginBottom: 12,
              }}
            >
              <strong style={{ fontSize: 15 }}>Xem trước khung hình &amp; Thiết bị</strong>
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
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(2, 6, 23, 0.76)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 120,
            padding: 16,
          }}
          onClick={() => setShowLanQrModal(false)}
        >
          <div
            className="card"
            onClick={(e) => e.stopPropagation()}
            style={{ width: '100%', maxWidth: 460, marginBottom: 0, textAlign: 'center' }}
          >
            <div className="page-header" style={{ marginBottom: 14, textAlign: 'left' }}>
              <div>
                <div className="page-title">
                  <Wifi size={19} /> Mở ChaosShortVideo trên Điện thoại
                </div>
                <div className="page-subtitle">
                  Tải thẳng ảnh &amp; video gốc vừa chụp từ iPhone / Android vào máy chủ qua Wi-Fi
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
                <label className="form-label">Chọn địa chỉ mạng nội bộ:</label>
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
                marginBottom: 12,
                boxShadow: '0 8px 24px rgba(0, 0, 0, 0.25)',
              }}
            >
              <img
                src={studioApi.getLanQrImageUrl(activeLanUrl)}
                alt="LAN Wi-Fi QR Code"
                style={{ width: 220, height: 220, display: 'block' }}
              />
            </div>

            <div
              className="step-box"
              style={{ textAlign: 'left', padding: '12px 14px', marginBottom: 12 }}
            >
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>
                Hướng dẫn kết nối nhanh (Không cần gửi vòng qua Zalo):
              </div>
              <div className="text-sub" style={{ fontSize: 12.6, lineHeight: 1.5 }}>
                1. Đảm bảo điện thoại bắt <strong>cùng mạng Wi-Fi</strong> với máy tính này.
                <br />
                2. Mở <strong>Camera điện thoại</strong> hướng vào hình trên để mở thẳng giao diện Studio.
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="input"
                readOnly
                value={activeLanUrl}
                style={{ flex: 1, fontWeight: 700, textAlign: 'center' }}
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
