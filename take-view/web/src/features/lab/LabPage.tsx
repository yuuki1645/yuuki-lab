/** Browse lab takes; one take opens in the analysis workbench. */

import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import LabWorkbench from "./analysis/LabWorkbench";
import { labApi } from "./api";
import { errorText } from "./errors";
import { L } from "./labels";
import type { LabDay, LabTakeMeta } from "./types";

function formatWhen(iso: string | null): string {
  if (!iso) return L.dash;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("ja-JP", { hour12: false });
}

function formatDuration(sec: number | null): string {
  if (sec == null || !Number.isFinite(sec)) return L.dash;
  const total = Math.max(0, Math.round(sec));
  const mins = Math.floor(total / 60);
  const rem = total % 60;
  return `${mins}:${String(rem).padStart(2, "0")}`;
}

export default function LabPage() {
  const { day: routeDay, takeId } = useParams();
  useEffect(() => {
    document.title = takeId ? `${L.title} ${takeId}` : L.title;
  }, [takeId]);

  return (
    <div className="page lab-page">
      <header className="lab-header">
        <div>
          <h2 className="page-title">{L.title}</h2>
          <p className="lab-lead">{L.lead}</p>
        </div>
        {takeId && routeDay ? (
          <Link className="btn btn-ghost" to={`/lab?day=${encodeURIComponent(routeDay)}`}>
            {L.back}
          </Link>
        ) : null}
      </header>
      {takeId && routeDay ? <LabWorkbench day={routeDay} takeId={takeId} /> : <TakeList />}
    </div>
  );
}

/** Day tabs and the takes of the chosen day. */
function TakeList() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedDay = searchParams.get("day") || "";
  const [days, setDays] = useState<LabDay[]>([]);
  const [root, setRoot] = useState("");
  const [available, setAvailable] = useState(true);
  const [takes, setTakes] = useState<LabTakeMeta[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Day index once; picks the newest day when none is in the URL.
  useEffect(() => {
    let cancel = false;
    labApi
      .getDays()
      .then((body) => {
        if (cancel) return;
        setDays(body.days);
        setRoot(body.root);
        setAvailable(body.available);
        if (!body.days.length) setLoading(false);
        setSearchParams(
          (current) => {
            if (current.get("day") || !body.days[0]) return current;
            const next = new URLSearchParams(current);
            next.set("day", body.days[0].day);
            return next;
          },
          { replace: true }
        );
      })
      .catch((err: unknown) => {
        if (!cancel) setError(errorText(err));
      });
    return () => {
      cancel = true;
    };
  }, [setSearchParams]);

  useEffect(() => {
    if (!selectedDay) return;
    let cancel = false;
    setLoading(true);
    labApi
      .getTakes(selectedDay)
      .then((body) => {
        if (!cancel) setTakes(body.takes);
      })
      .catch((err: unknown) => {
        if (!cancel) setError(errorText(err));
      })
      .finally(() => {
        if (!cancel) setLoading(false);
      });
    return () => {
      cancel = true;
    };
  }, [selectedDay]);

  return (
    <>
      {error ? <p className="lab-error">{error}</p> : null}
      {!available ? (
        <section className="card">
          <p>{L.rootMissing}</p>
          <p className="lab-muted">
            {L.rootLabel}: {root}
          </p>
        </section>
      ) : (
        <>
          <div className="lab-day-row" role="tablist">
            {days.map((item) => (
              <button
                key={item.day}
                type="button"
                className={item.day === selectedDay ? "btn btn-primary" : "btn"}
                onClick={() => setSearchParams({ day: item.day })}
              >
                {item.day}
                <span className="lab-day-count">{item.take_count}</span>
              </button>
            ))}
          </div>
          {loading ? <p className="lab-muted">{L.loading}</p> : null}
          {!loading && takes.length === 0 ? <p className="lab-muted">{L.noDays}</p> : null}
          {takes.length > 0 ? (
            <div className="card lab-table-wrap">
              <table className="lab-table">
                <thead>
                  <tr>
                    <th>{L.takes}</th>
                    <th>{L.started}</th>
                    <th>{L.duration}</th>
                    <th>{L.samples}</th>
                    <th>{L.stop}</th>
                    <th>{L.notes}</th>
                  </tr>
                </thead>
                <tbody>
                  {takes.map((take) => (
                    <tr key={`${take.side ?? "robot"}-${take.take_id}`}>
                      <td>
                        <Link
                          className="lab-take-link"
                          to={
                            take.side === "sim"
                              ? `/lab/${selectedDay}/${take.take_id}?side=sim`
                              : `/lab/${selectedDay}/${take.take_id}`
                          }
                        >
                          {take.take_id}
                        </Link>
                        {take.recording ? <span className="lab-badge">{L.recording}</span> : null}
                        {take.side === "sim" ? <span className="lab-badge">{L.formatSim}</span> : null}
                        {take.format_id === "core_take_v2" ? <span className="lab-badge">{L.formatV2}</span> : null}
                        {!take.supported ? <span className="lab-badge">{L.unsupported}</span> : null}
                      </td>
                      <td>{formatWhen(take.started_at)}</td>
                      <td>{formatDuration(take.duration_sec)}</td>
                      <td>
                        {take.side === "sim"
                          ? `${L.policyTitle} ${take.policy_count ?? take.sample_count ?? L.dash}`
                          : (take.sample_count ?? L.dash)}
                        {take.side !== "sim" && take.policy_count != null ? ` / ${L.policyTitle} ${take.policy_count}` : ""}
                      </td>
                      <td>{take.stop_reason || L.dash}</td>
                      <td className="lab-notes">{take.notes || L.dash}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}
