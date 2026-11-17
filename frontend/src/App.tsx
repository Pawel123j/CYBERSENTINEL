import {
  useQuery,
  type UseQueryResult,
} from "@tanstack/react-query";

import {
  fetchHealth,
  HealthEndpointError,
  type HealthResponse,
} from "./api/health";

const REFRESH_INTERVAL_MS = 15_000;

type CheckKind = "live" | "ready";
type CheckState = "checking" | "healthy" | "unhealthy";

interface HealthCardProps {
  kind: CheckKind;
  query: UseQueryResult<HealthResponse, Error>;
}

const checkContent: Record<
  CheckKind,
  { title: string; endpoint: string; description: string }
> = {
  live: {
    title: "Backend liveness",
    endpoint: "/api/health/live",
    description: "Confirms that the API process can answer an HTTP request.",
  },
  ready: {
    title: "Service readiness",
    endpoint: "/api/health/ready",
    description:
      "Confirms that the API reports itself ready to serve application traffic.",
  },
};

const stateStyles: Record<
  CheckState,
  { label: string; badge: string; dot: string; edge: string }
> = {
  checking: {
    label: "Checking",
    badge: "border-slate-600/80 bg-slate-800/70 text-slate-300",
    dot: "bg-slate-400",
    edge: "from-slate-500/70",
  },
  healthy: {
    label: "Available",
    badge: "border-emerald-400/25 bg-emerald-400/10 text-emerald-200",
    dot: "bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]",
    edge: "from-emerald-400/80",
  },
  unhealthy: {
    label: "Unavailable",
    badge: "border-rose-400/25 bg-rose-400/10 text-rose-200",
    dot: "bg-rose-400 shadow-[0_0_12px_rgba(251,113,133,0.65)]",
    edge: "from-rose-400/80",
  },
};

const timestampFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

function getCheckState(
  query: UseQueryResult<HealthResponse, Error>
): CheckState {
  if (query.isPending) {
    return "checking";
  }

  return query.isError ? "unhealthy" : "healthy";
}

function formatError(error: Error): string {
  if (error instanceof HealthEndpointError) {
    return `The backend responded with HTTP ${error.statusCode}.`;
  }

  if (error.name === "TypeError") {
    return "The endpoint could not be reached through the API proxy.";
  }

  return error.message;
}

function formatPayload(payload: unknown): string {
  if (typeof payload === "string") {
    return payload;
  }

  return JSON.stringify(payload, null, 2);
}

function HealthCard({ kind, query }: HealthCardProps) {
  const content = checkContent[kind];
  const state = getCheckState(query);
  const visual = stateStyles[state];
  const timestamp = query.data?.checkedAt
    ? timestampFormatter.format(new Date(query.data.checkedAt))
    : null;

  return (
    <article className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-slate-950/55 p-5 shadow-2xl shadow-black/20 backdrop-blur-xl sm:p-6">
      <div
        aria-hidden="true"
        className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${visual.edge} via-transparent to-transparent`}
      />

      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[0.68rem] tracking-[0.18em] text-cyan-200/60 uppercase">
            {content.endpoint}
          </p>
          <h2 className="mt-2 text-lg font-semibold tracking-tight text-white">
            {content.title}
          </h2>
        </div>

        <span
          className={`inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${visual.badge}`}
        >
          <span
            aria-hidden="true"
            className={`h-1.5 w-1.5 rounded-full ${visual.dot}`}
          />
          {kind === "ready" && state === "unhealthy"
            ? "Not ready"
            : visual.label}
        </span>
      </div>

      <p className="mt-5 max-w-md text-sm leading-6 text-slate-400">
        {content.description}
      </p>

      <div className="mt-7 border-t border-white/[0.07] pt-5" aria-live="polite">
        {query.isPending ? (
          <p className="text-sm text-slate-300">Waiting for the first response…</p>
        ) : null}

        {query.isError ? (
          <div>
            <p className="text-sm font-medium text-rose-200">
              {formatError(query.error)}
            </p>
            {timestamp ? (
              <p className="mt-1.5 text-xs text-slate-500">
                Last successful response at {timestamp}
              </p>
            ) : null}
          </div>
        ) : null}

        {query.isSuccess ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-emerald-200">
              HTTP {query.data.statusCode} · successful response
            </p>
            <p className="text-xs text-slate-500">
              Checked at {timestamp}
              {query.isFetching ? " · refreshing" : ""}
            </p>
          </div>
        ) : null}
      </div>

      {query.data ? (
        <details className="group mt-4 rounded-xl border border-white/[0.06] bg-black/15 px-4 py-3">
          <summary className="cursor-pointer select-none text-xs font-medium text-slate-400 outline-none transition hover:text-slate-200 focus-visible:text-cyan-200">
            Inspect last successful response
          </summary>
          <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-5 text-cyan-100/70">
            {formatPayload(query.data.payload)}
          </pre>
        </details>
      ) : null}
    </article>
  );
}

function getFoundationState(
  liveQuery: UseQueryResult<HealthResponse, Error>,
  readyQuery: UseQueryResult<HealthResponse, Error>
) {
  if (liveQuery.isPending || readyQuery.isPending) {
    return {
      label: "Checking backend",
      detail: "Waiting for the first liveness and readiness responses.",
      dot: "bg-slate-400",
    };
  }

  if (liveQuery.isError) {
    return {
      label: "Backend unavailable",
      detail: "The frontend is running, but the API liveness check failed.",
      dot: "bg-rose-400 shadow-[0_0_14px_rgba(251,113,133,0.7)]",
    };
  }

  if (readyQuery.isError) {
    return {
      label: "Backend live, not ready",
      detail: "The API responds, but its readiness contract is not satisfied.",
      dot: "bg-amber-300 shadow-[0_0_14px_rgba(252,211,77,0.65)]",
    };
  }

  return {
    label: "Foundation online",
    detail: "Both backend health contracts are returning successful responses.",
    dot: "bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,0.8)]",
  };
}

export default function App() {
  const liveQuery = useQuery({
    queryKey: ["health", "live"],
    queryFn: ({ signal }) => fetchHealth(checkContent.live.endpoint, signal),
    refetchInterval: REFRESH_INTERVAL_MS,
  });
  const readyQuery = useQuery({
    queryKey: ["health", "ready"],
    queryFn: ({ signal }) => fetchHealth(checkContent.ready.endpoint, signal),
    refetchInterval: REFRESH_INTERVAL_MS,
  });
  const foundation = getFoundationState(liveQuery, readyQuery);
  const isRefreshing = liveQuery.isFetching || readyQuery.isFetching;

  const refreshHealth = () => {
    void Promise.all([liveQuery.refetch(), readyQuery.refetch()]);
  };

  return (
    <div className="app-grid relative min-h-screen overflow-hidden bg-[#07100f] text-slate-100">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[34rem] bg-[radial-gradient(circle_at_18%_8%,rgba(34,211,238,0.13),transparent_31%),radial-gradient(circle_at_82%_0%,rgba(52,211,153,0.09),transparent_27%)]"
      />

      <header className="relative border-b border-white/[0.07] bg-[#07100f]/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-300/[0.08] font-mono text-xs font-bold tracking-wider text-cyan-200 shadow-[inset_0_0_18px_rgba(34,211,238,0.05)]">
              CS
            </div>
            <div>
              <p className="text-sm font-semibold tracking-tight text-white">
                CyberSentinel
              </p>
              <p className="text-[0.66rem] tracking-[0.16em] text-slate-500 uppercase">
                Security monitoring platform
              </p>
            </div>
          </div>

          <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 font-mono text-[0.66rem] tracking-[0.13em] text-slate-400 uppercase">
            Stage 01 · v0.1.0
          </span>
        </div>
      </header>

      <main className="relative mx-auto max-w-6xl px-5 py-12 sm:px-8 sm:py-16">
        <section className="grid items-end gap-9 lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)]">
          <div>
            <p className="font-mono text-xs tracking-[0.2em] text-cyan-300/75 uppercase">
              Project foundation
            </p>
            <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-[-0.035em] text-balance text-white sm:text-5xl">
              A clear signal before the security data arrives.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
              This first operational surface reports only the backend health
              contracts. No demo alerts, device totals, or invented risk scores.
            </p>
          </div>

          <div className="rounded-2xl border border-white/[0.08] bg-white/[0.035] p-5 backdrop-blur-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium tracking-[0.15em] text-slate-500 uppercase">
                  Current state
                </p>
                <p className="mt-2 text-lg font-semibold text-white">
                  {foundation.label}
                </p>
              </div>
              <span
                aria-hidden="true"
                className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${foundation.dot}`}
              />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-400">
              {foundation.detail}
            </p>
            <button
              type="button"
              onClick={refreshHealth}
              disabled={isRefreshing}
              className="mt-5 inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/[0.07] px-4 text-sm font-semibold text-cyan-100 transition hover:border-cyan-300/35 hover:bg-cyan-300/[0.11] focus-visible:ring-2 focus-visible:ring-cyan-300/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#07100f] focus-visible:outline-none disabled:cursor-wait disabled:opacity-60"
            >
              {isRefreshing ? "Checking endpoints…" : "Check again"}
            </button>
          </div>
        </section>

        <section
          aria-label="Backend health checks"
          className="mt-10 grid gap-4 lg:grid-cols-2"
        >
          <HealthCard kind="live" query={liveQuery} />
          <HealthCard kind="ready" query={readyQuery} />
        </section>

        <section className="mt-6 rounded-2xl border border-white/[0.07] bg-black/15 px-5 py-5 sm:flex sm:items-start sm:justify-between sm:gap-10 sm:px-6">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">
              Scope of this checkpoint
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Readiness is determined by the backend response, not inferred by
              the browser. Development traffic uses the Vite proxy; the
              production container routes the same <code>/api</code> path through
              Nginx to the backend service.
            </p>
          </div>
          <p className="mt-4 shrink-0 font-mono text-[0.68rem] leading-5 tracking-[0.11em] text-slate-600 uppercase sm:mt-0 sm:text-right">
            Automatic refresh
            <br />
            every 15 seconds
          </p>
        </section>
      </main>
    </div>
  );
}
