/** Shows whether the local worker has checked in recently. */
export function WorkerBadge({ lastSeenAt }: { lastSeenAt: Date | null }) {
  if (!lastSeenAt) {
    return (
      <span className="pill warn">
        <span className="dot" />
        worker offline
      </span>
    );
  }
  const ageMs = Date.now() - new Date(lastSeenAt).getTime();
  const online = ageMs < 2 * 60 * 1000; // seen in last 2 min
  const mins = Math.round(ageMs / 60000);
  return (
    <span className={online ? "pill ok" : "pill warn"}>
      <span className="dot" />
      {online ? "worker online" : `worker last seen ${mins}m ago`}
    </span>
  );
}
