import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, schedulesApi, schoolDataApi } from "./api/client";
import { AppShell, type Screen } from "./components/AppShell";
import { Dashboard } from "./components/Dashboard";
import { SchoolDataTables } from "./components/SchoolDataTables";
import { Timetable } from "./components/Timetable";
import { Versions } from "./components/Versions";
import type { Schedule, ScheduleComparison, ScheduleVersion, SchoolData } from "./types";

const emptyData: SchoolData = { teachers: [], rooms: [], groups: [], activities: [] };
const storageKey = "school-ai-demo-schedule-id";

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === "SCHEDULE_INFEASIBLE") return "No valid timetable fits the current resources and time slots. Nothing was saved.";
    if (error.code === "SOLVER_STATUS_UNKNOWN") return "The solver could not confirm a timetable in time. Nothing was saved; try again.";
    if (error.code === "SCHEDULING_DATA_INCOMPLETE") return "School scheduling data is not ready yet. Load the synthetic demo data, then try again.";
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export function App() {
  const [screen, setScreen] = useState<Screen>("dashboard");
  const [data, setData] = useState<SchoolData>(emptyData);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [versions, setVersions] = useState<ScheduleVersion[]>([]);
  const [published, setPublished] = useState<ScheduleVersion | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<ScheduleVersion | null>(null);
  const [comparison, setComparison] = useState<ScheduleComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [publishingId, setPublishingId] = useState<number | null>(null);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshSchedule = useCallback(async (scheduleId: number, preferredVersionId?: number) => {
    const [nextSchedule, nextVersions, nextPublished] = await Promise.all([
      schedulesApi.get(scheduleId), schedulesApi.versions(scheduleId), schedulesApi.published(scheduleId),
    ]);
    setSchedule(nextSchedule); setVersions(nextVersions); setPublished(nextPublished);
    const preferred = nextVersions.find((item) => item.id === preferredVersionId);
    const latestDraft = [...nextVersions].reverse().find((item) => item.status === "DRAFT");
    setSelectedVersion(preferred ?? latestDraft ?? nextPublished ?? nextVersions.at(-1) ?? null);
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [teachers, rooms, groups, activities] = await Promise.all([
        schoolDataApi.teachers(), schoolDataApi.rooms(), schoolDataApi.groups(), schoolDataApi.activities(),
      ]);
      setData({ teachers, rooms, groups, activities });
      const storedId = Number(window.localStorage.getItem(storageKey));
      if (storedId) {
        try { await refreshSchedule(storedId); }
        catch (scheduleError) {
          if (scheduleError instanceof ApiError && scheduleError.status === 404) window.localStorage.removeItem(storageKey);
          else throw scheduleError;
        }
      }
    } catch (loadError) { setError(errorMessage(loadError)); }
    finally { setLoading(false); }
  }, [refreshSchedule]);

  useEffect(() => { void load(); }, [load]);

  const generate = async () => {
    if (generating) return;
    setGenerating(true); setError(null); setNotice(null);
    try {
      let activeSchedule = schedule;
      if (!activeSchedule) {
        activeSchedule = await schedulesApi.create("School AI Demo Timetable");
        window.localStorage.setItem(storageKey, String(activeSchedule.id));
        setSchedule(activeSchedule);
      }
      const result = await schedulesApi.generateDraft(activeSchedule.id);
      await refreshSchedule(activeSchedule.id, result.version.id);
      setNotice(`Draft version ${result.version.version_number} created by CP-SAT in ${result.solve_duration_seconds.toFixed(3)}s.`);
      setScreen("timetable");
    } catch (generationError) { setError(errorMessage(generationError)); }
    finally { setGenerating(false); }
  };

  const publish = async (version: ScheduleVersion) => {
    if (!schedule || !window.confirm(`Publish version ${version.version_number}? This will supersede the current published timetable.`)) return;
    setPublishingId(version.id); setError(null);
    try {
      await schedulesApi.publish(schedule.id, version.id);
      await refreshSchedule(schedule.id, version.id);
      setNotice(`Version ${version.version_number} is now published.`);
    } catch (publishError) { setError(errorMessage(publishError)); }
    finally { setPublishingId(null); }
  };

  const compare = async (fromId: number, toId: number) => {
    if (!schedule) return;
    setComparing(true); setError(null);
    try { setComparison(await schedulesApi.compare(schedule.id, fromId, toId)); }
    catch (compareError) { setError(errorMessage(compareError)); }
    finally { setComparing(false); }
  };

  const latestDraft = useMemo(() => [...versions].reverse().find((item) => item.status === "DRAFT") ?? null, [versions]);
  return (
    <AppShell screen={screen} onNavigate={setScreen} apiOnline={!error || data.teachers.length > 0}>
      {loading ? <div className="loading-screen"><span className="spinner large" /><strong>Connecting to School AI…</strong><p>Loading resources and schedule state.</p></div> : (
        <div className="page-content">
          {error && <div className="alert error" role="alert"><div><strong>We couldn’t complete that action.</strong><p>{error}</p></div><button onClick={() => void load()}>Retry connection</button></div>}
          {notice && <div className="alert success" role="status"><div><strong>Schedule updated</strong><p>{notice}</p></div><button aria-label="Dismiss notification" onClick={() => setNotice(null)}>×</button></div>}
          {screen === "dashboard" && <Dashboard data={data} schedule={schedule} published={published} latestDraft={latestDraft} generating={generating} onGenerate={() => void generate()} onOpenTimetable={() => { setSelectedVersion(published); setScreen("timetable"); }} />}
          {screen === "data" && <SchoolDataTables data={data} />}
          {screen === "timetable" && <Timetable version={selectedVersion} data={data} />}
          {screen === "versions" && <Versions schedule={schedule} versions={versions} comparison={comparison} publishingId={publishingId} comparing={comparing} onSelect={(version) => { setSelectedVersion(version); setScreen("timetable"); }} onPublish={(version) => void publish(version)} onCompare={(from, to) => void compare(from, to)} data={data} />}
        </div>
      )}
    </AppShell>
  );
}
