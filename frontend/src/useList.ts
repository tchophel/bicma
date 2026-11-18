import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "./api";

export function useList<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    api<T>(path).then((d) => { setData(d); setErr(""); }).catch((x) => setErr((x as ApiError).message)).finally(() => setLoading(false));
  }, [path]);
  useEffect(reload, [reload]);
  return { data, err, loading, reload };
}
