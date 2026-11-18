import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, withMinTime } from "./api";

export function useList<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const seen = useRef(false); // the first load of a screen shows the spinner for a moment; later reloads are instant
  const reload = useCallback(() => {
    setLoading(true);
    (seen.current ? api<T>(path) : withMinTime(api<T>(path))).then((d) => { seen.current = true; setData(d); setErr(""); }).catch((x) => setErr((x as ApiError).message)).finally(() => setLoading(false));
  }, [path]);
  useEffect(reload, [reload]);
  return { data, err, loading, reload };
}
