import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Chip, IconButton, LinearProgress, Paper, Stack, Tab, Tabs, Tooltip, Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import StopCircleOutlinedIcon from "@mui/icons-material/StopCircleOutlined";
import { ACTIVE_STATUSES, api, jobFileUrl } from "../api";

const STATUS = {
  queued: { label: "Queued", color: "default" },
  preparing: { label: "Preparing", color: "info" },
  running: { label: "Generating", color: "primary" },
  done: { label: "Done", color: "success" },
  error: { label: "Failed", color: "error" },
  cancelled: { label: "Cancelled", color: "default" },
};

function formatDuration(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return h ? `${h}h ${m}m` : m ? `${m}m ${s % 60}s` : `${s}s`;
}

/** Elapsed time that ticks every second while the job runs. */
function useElapsed(job) {
  const [now, setNow] = useState(Date.now());
  const running = ACTIVE_STATUSES.includes(job.status) && job.started_at;
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);
  if (!job.started_at) return null;
  const end = job.finished_at ? new Date(job.finished_at).getTime() : now;
  return end - new Date(job.started_at).getTime();
}

function Thumb({ src, video, label }) {
  const sx = { width: 56, height: 72, objectFit: "cover", borderRadius: 1, bgcolor: "action.selected", display: "block" };
  return (
    <Tooltip title={label}>
      {video ? <Box component="video" src={src} muted playsInline preload="metadata" sx={sx} /> : <Box component="img" src={src} alt={label} sx={sx} />}
    </Tooltip>
  );
}

export default function JobCard({ job, onChanged }) {
  const [view, setView] = useState("result");
  const [actionError, setActionError] = useState(null);
  const elapsed = useElapsed(job);
  const active = ACTIVE_STATUSES.includes(job.status);
  const status = STATUS[job.status] ?? { label: job.status, color: "default" };
  const o = job.options;
  const has = (kind) => job.files.includes(kind);
  const shown = view === "pose" && has("pose") ? "pose" : has("result") ? "result" : has("pose") ? "pose" : null;

  const act = async (fn) => {
    setActionError(null);
    try {
      await fn(job.id);
      onChanged();
    } catch (e) {
      setActionError(e.message);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: "flex-start" }}>
        {has("image") && <Thumb src={jobFileUrl(job.id, "image")} label="Character" />}
        {has("video") && <Thumb src={jobFileUrl(job.id, "video")} video label="Motion" />}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              #{job.id}
            </Typography>
            <Chip size="small" label={status.label} color={status.color} variant={active ? "filled" : "outlined"} />
            <Box sx={{ flex: 1 }} />
            {elapsed !== null && (
              <Typography variant="caption" color="text.secondary" sx={{ fontVariantNumeric: "tabular-nums" }}>
                {formatDuration(elapsed)}
              </Typography>
            )}
            {active ? (
              <Tooltip title="Cancel">
                <span>
                  <IconButton size="small" disabled={job.cancel_requested} onClick={() => act(api.cancelJob)}>
                    <StopCircleOutlinedIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
            ) : (
              <Tooltip title="Delete">
                <IconButton size="small" onClick={() => act(api.deleteJob)}>
                  <DeleteOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Stack>
          <Typography variant="body2" noWrap title={job.prompt} sx={{ mt: 0.25 }}>
            {job.prompt}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {[
              job.width && `${job.width}×${job.height}`,
              job.frames ? `${(job.frames / 16).toFixed(1)}s (${job.frames} frames)` : `≤${o.max_seconds}s`,
              job.segments && `${job.segments} segment${job.segments > 1 ? "s" : ""}`,
              `${o.steps} steps`,
              `seed ${o.seed}`,
              o.retarget && "retarget",
            ]
              .filter(Boolean)
              .join(" · ")}
          </Typography>
        </Box>
      </Stack>

      {active && (
        <Box sx={{ mt: 1.5 }}>
          <LinearProgress
            variant={job.status === "running" && job.progress > 0.02 ? "determinate" : "indeterminate"}
            value={job.progress * 100}
          />
          <Stack direction="row" sx={{ mt: 0.5, justifyContent: "space-between" }}>
            <Typography variant="caption" color="text.secondary">
              {job.message}
            </Typography>
            {job.status === "running" && (
              <Typography variant="caption" color="text.secondary">
                {Math.round(job.progress * 100)}%
              </Typography>
            )}
          </Stack>
        </Box>
      )}

      {job.status === "error" && (
        <Alert severity="error" sx={{ mt: 1.5, wordBreak: "break-word" }}>
          {job.error}
        </Alert>
      )}
      {actionError && (
        <Alert severity="warning" sx={{ mt: 1.5 }} onClose={() => setActionError(null)}>
          {actionError}
        </Alert>
      )}

      {shown && (
        <Box sx={{ mt: 1.5 }}>
          {has("result") && has("pose") && (
            <Tabs value={shown} onChange={(_, v) => setView(v)} sx={{ minHeight: 36, "& .MuiTab-root": { minHeight: 36, py: 0 } }}>
              <Tab value="result" label="Result" />
              <Tab value="pose" label="Detected pose" />
            </Tabs>
          )}
          <Box
            key={shown}
            component="video"
            src={jobFileUrl(job.id, shown)}
            controls
            loop
            playsInline
            autoPlay={shown === "result"}
            muted={shown === "pose"}
            sx={{ display: "block", width: "100%", maxHeight: 520, bgcolor: "black", borderRadius: 1, mt: 1 }}
          />
          {shown === "result" && (
            <Button
              size="small"
              startIcon={<DownloadIcon />}
              href={jobFileUrl(job.id, "result", { download: true })}
              sx={{ mt: 1 }}
            >
              Download
            </Button>
          )}
        </Box>
      )}
    </Paper>
  );
}
