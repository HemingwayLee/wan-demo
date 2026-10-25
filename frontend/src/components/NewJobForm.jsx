import { useState } from "react";
import {
  Alert, Box, Button, Collapse, FormControlLabel, LinearProgress, MenuItem, Paper, Slider, Stack,
  Switch, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from "@mui/material";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import MovieOutlinedIcon from "@mui/icons-material/MovieOutlined";
import TuneIcon from "@mui/icons-material/Tune";
import { createJob } from "../api";
import UploadBox from "./UploadBox";

const FPS = 16;
const SEGMENT = 77;
const OVERLAP = 5;
const MAX_SECONDS = 20;

/** Same segment plan as the backend: 77-frame chunks, each continuing from the last 5 frames. */
function segmentCount(seconds) {
  const frames = Math.round(seconds * FPS);
  return frames <= SEGMENT ? 1 : 1 + Math.ceil((frames - SEGMENT) / (SEGMENT - OVERLAP));
}

export default function NewJobForm({ onCreated }) {
  const [image, setImage] = useState(null);
  const [video, setVideo] = useState(null);
  const [videoDuration, setVideoDuration] = useState(null);
  const [prompt, setPrompt] = useState("a person is dancing");
  const [seconds, setSeconds] = useState(5);
  const [resolution, setResolution] = useState(480);
  const [steps, setSteps] = useState(4);
  const [fit, setFit] = useState("pad");
  const [retarget, setRetarget] = useState(false);
  const [seed, setSeed] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [upload, setUpload] = useState(null); // 0–1 while uploading
  const [error, setError] = useState(null);

  const maxSeconds = videoDuration ? Math.max(1, Math.min(MAX_SECONDS, Math.floor(videoDuration))) : MAX_SECONDS;
  const length = Math.min(seconds, maxSeconds);
  const segments = segmentCount(videoDuration ? Math.min(length, videoDuration) : length);

  const submit = async () => {
    setError(null);
    setUpload(0);
    try {
      await createJob(
        { image, video, prompt, max_seconds: length, resolution, steps, fit, retarget, seed },
        { onProgress: setUpload }
      );
      onCreated();
    } catch (e) {
      setError(e.message);
    } finally {
      setUpload(null);
    }
  };

  const busy = upload !== null;

  return (
    <Paper variant="outlined" sx={{ p: 2.5 }}>
      <Stack spacing={2.5}>
        <Box>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            New dance
          </Typography>
          <Typography variant="body2" color="text.secondary">
            The person in the image performs the moves from the video.
          </Typography>
        </Box>

        <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5 }}>
          <UploadBox
            kind="image"
            label="Character"
            hint="Photo of one person, full body works best"
            icon={<PersonOutlineIcon fontSize="inherit" />}
            file={image}
            onChange={setImage}
            disabled={busy}
          />
          <UploadBox
            kind="video"
            label="Motion"
            hint="Dance video with one clearly visible person"
            icon={<MovieOutlinedIcon fontSize="inherit" />}
            file={video}
            onChange={(f) => {
              setVideo(f);
              setVideoDuration(null);
            }}
            onVideoInfo={({ duration }) => setVideoDuration(duration)}
            disabled={busy}
          />
        </Box>

        <TextField
          label="Prompt"
          size="small"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          multiline
          maxRows={3}
          disabled={busy}
        />

        <Box>
          <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "baseline" }}>
            <Typography variant="body2">Length</Typography>
            <Typography variant="body2" color="text.secondary">
              {length}s · {segments} segment{segments > 1 ? "s" : ""}
            </Typography>
          </Stack>
          <Slider
            size="small"
            min={1}
            max={maxSeconds}
            step={1}
            marks
            value={length}
            onChange={(_, v) => setSeconds(v)}
            disabled={busy}
          />
          <Typography variant="caption" color="text.secondary">
            Each segment covers ~5 s and is generated one after another, so time grows with length.
          </Typography>
        </Box>

        <Box>
          <Typography variant="body2" sx={{ mb: 0.75 }}>
            Resolution (short side)
          </Typography>
          <ToggleButtonGroup
            exclusive
            fullWidth
            size="small"
            value={resolution}
            onChange={(_, v) => v && setResolution(v)}
            disabled={busy}
          >
            <ToggleButton value={480}>480p</ToggleButton>
            <ToggleButton value={576}>576p</ToggleButton>
            <ToggleButton value={720}>720p</ToggleButton>
          </ToggleButtonGroup>
          {resolution > 480 && (
            <Typography variant="caption" color="warning.main">
              Above 480p needs much more memory and time; it may run out of memory on 36 GB.
            </Typography>
          )}
        </Box>

        <Box>
          <Button
            size="small"
            startIcon={<TuneIcon />}
            onClick={() => setAdvanced((a) => !a)}
            sx={{ ml: -0.5 }}
          >
            {advanced ? "Hide" : "More"} options
          </Button>
          <Collapse in={advanced}>
            <Stack spacing={2} sx={{ pt: 1.5 }}>
              <Stack direction="row" spacing={1.5}>
                <TextField
                  select
                  size="small"
                  label="Steps"
                  value={steps}
                  onChange={(e) => setSteps(e.target.value)}
                  sx={{ flex: 1 }}
                  disabled={busy}
                >
                  {[4, 6, 8].map((s) => (
                    <MenuItem key={s} value={s}>
                      {s}
                      {s === 4 ? " (fastest)" : ""}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  size="small"
                  label="Seed"
                  placeholder="Random"
                  value={seed}
                  onChange={(e) => setSeed(e.target.value.replace(/\D/g, ""))}
                  sx={{ flex: 1 }}
                  disabled={busy}
                />
              </Stack>
              <Box>
                <Typography variant="body2" sx={{ mb: 0.75 }}>
                  Fit image to video frame
                </Typography>
                <ToggleButtonGroup
                  exclusive
                  fullWidth
                  size="small"
                  value={fit}
                  onChange={(_, v) => v && setFit(v)}
                  disabled={busy}
                >
                  <ToggleButton value="pad">Pad (keep all)</ToggleButton>
                  <ToggleButton value="crop">Crop (fill)</ToggleButton>
                </ToggleButtonGroup>
              </Box>
              <FormControlLabel
                control={<Switch checked={retarget} onChange={(e) => setRetarget(e.target.checked)} disabled={busy} />}
                label={
                  <Box>
                    <Typography variant="body2">Retarget pose</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Match the skeleton to the character's body proportions
                    </Typography>
                  </Box>
                }
              />
            </Stack>
          </Collapse>
        </Box>

        {error && <Alert severity="error">{error}</Alert>}

        {busy ? (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              Uploading… {Math.round(upload * 100)}%
            </Typography>
            <LinearProgress variant="determinate" value={upload * 100} />
          </Box>
        ) : (
          <Button variant="contained" size="large" disabled={!image || !video} onClick={submit}>
            Generate
          </Button>
        )}
      </Stack>
    </Paper>
  );
}
