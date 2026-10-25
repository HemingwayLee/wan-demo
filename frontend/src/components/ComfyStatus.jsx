import { useEffect, useState } from "react";
import { Chip, Tooltip } from "@mui/material";
import { api } from "../api";

/** ComfyUI reachability and model check, refreshed every 15 s. */
export default function ComfyStatus() {
  const [status, setStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api
        .comfyui()
        .then((s) => !cancelled && setStatus(s))
        .catch(() => !cancelled && setStatus({ online: false, missing_models: [] }));
    load();
    const id = setInterval(load, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!status) return null;

  let color = "success";
  let label = `ComfyUI · ${status.device?.toUpperCase() ?? "ready"}`;
  let tip = `${status.url} · v${status.version} · ${status.model}`;
  if (!status.online) {
    color = "error";
    label = "ComfyUI offline";
    tip = "Start it on the Mac with scripts/run_comfyui.sh";
  } else if (status.missing_models.length) {
    color = "warning";
    label = `${status.missing_models.length} model(s) missing`;
    tip = `Run scripts/download_models.sh. Missing: ${status.missing_models.join(", ")}`;
  }

  return (
    <Tooltip title={tip}>
      <Chip size="small" variant="outlined" color={color} label={label} />
    </Tooltip>
  );
}
