import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, AppBar, Box, Container, Stack, Toolbar, Typography } from "@mui/material";
import { ACTIVE_STATUSES, api } from "./api";
import ComfyStatus from "./components/ComfyStatus";
import JobCard from "./components/JobCard";
import NewJobForm from "./components/NewJobForm";
import ThemeToggle from "./components/ThemeToggle";

/** Jobs list, polled fast while something is generating and slowly otherwise. */
function useJobs() {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState(null);
  const timer = useRef();

  const refresh = useCallback(async () => {
    clearTimeout(timer.current);
    let active = false;
    try {
      const list = await api.listJobs();
      setJobs(list);
      setError(null);
      active = list.some((j) => ACTIVE_STATUSES.includes(j.status));
    } catch (e) {
      setError(e.message);
    }
    timer.current = setTimeout(refresh, active ? 2000 : 10000);
  }, []);

  useEffect(() => {
    refresh();
    return () => clearTimeout(timer.current);
  }, [refresh]);

  return { jobs, error, refresh };
}

export default function App() {
  const { jobs, error, refresh } = useJobs();

  return (
    <Box sx={{ minHeight: "100dvh" }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar variant="dense" sx={{ gap: 1.5 }}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            wan-demo
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ flex: 1, display: { xs: "none", sm: "block" } }}>
            Dance transfer · Wan2.2-Animate
          </Typography>
          <Box sx={{ flex: { xs: 1, sm: 0 } }} />
          <ComfyStatus />
          <ThemeToggle />
        </Toolbar>
      </AppBar>

      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Box
          sx={{
            display: "grid",
            gap: 3,
            gridTemplateColumns: { xs: "1fr", md: "400px 1fr" },
            alignItems: "start",
          }}
        >
          <Box sx={{ position: { md: "sticky" }, top: { md: 72 } }}>
            <NewJobForm onCreated={refresh} />
          </Box>

          <Stack spacing={2}>
            <Typography variant="subtitle2" color="text.secondary">
              Generations
            </Typography>
            {error && <Alert severity="error">Can't load jobs: {error}</Alert>}
            {!error && jobs.length === 0 && (
              <Box
                sx={{
                  border: 1, borderColor: "divider", borderStyle: "dashed", borderRadius: 2,
                  p: 5, textAlign: "center", color: "text.secondary",
                }}
              >
                <Typography>No generations yet.</Typography>
                <Typography variant="body2">
                  Upload a character image and a dance video to make the character dance.
                </Typography>
              </Box>
            )}
            {jobs.map((job) => (
              <JobCard key={job.id} job={job} onChanged={refresh} />
            ))}
          </Stack>
        </Box>
      </Container>
    </Box>
  );
}
