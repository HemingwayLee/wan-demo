import { useEffect, useRef, useState } from "react";
import { Box, IconButton, Tooltip, Typography } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";

/** Click-or-drop file picker with an image/video preview. `kind` is "image" or "video". */
export default function UploadBox({ kind, label, hint, icon, file, onChange, onVideoInfo, disabled }) {
  const input = useRef();
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    if (!file) return setPreview(null);
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const pick = (files) => {
    const next = [...files].find((f) => f.type.startsWith(`${kind}/`));
    if (next) onChange(next);
  };

  return (
    <Box
      onClick={() => !disabled && !file && input.current.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) pick(e.dataTransfer.files);
      }}
      sx={{
        position: "relative",
        aspectRatio: "3 / 4",
        borderRadius: 2,
        border: 2,
        borderStyle: file ? "solid" : "dashed",
        borderColor: dragging ? "primary.main" : "divider",
        bgcolor: dragging ? "action.hover" : "action.selected",
        overflow: "hidden",
        cursor: file || disabled ? "default" : "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        transition: "border-color .15s, background-color .15s",
        "&:hover": !file && !disabled ? { borderColor: "primary.main" } : {},
      }}
    >
      <input
        ref={input}
        type="file"
        accept={`${kind}/*`}
        hidden
        onChange={(e) => {
          pick(e.target.files);
          e.target.value = "";
        }}
      />
      {preview && kind === "image" && (
        <Box component="img" src={preview} alt="" sx={{ width: "100%", height: "100%", objectFit: "contain" }} />
      )}
      {preview && kind === "video" && (
        <Box
          component="video"
          src={preview}
          muted
          loop
          autoPlay
          playsInline
          onLoadedMetadata={(e) => onVideoInfo?.({ duration: e.currentTarget.duration })}
          sx={{ width: "100%", height: "100%", objectFit: "contain", bgcolor: "black" }}
        />
      )}
      {!file && (
        <Box sx={{ textAlign: "center", px: 1.5, color: "text.secondary" }}>
          <Box sx={{ fontSize: 34, lineHeight: 1, mb: 1, color: "primary.main" }}>{icon}</Box>
          <Typography variant="subtitle2" color="text.primary">
            {label}
          </Typography>
          <Typography variant="caption">{hint}</Typography>
        </Box>
      )}
      {file && (
        <>
          <Typography
            variant="caption"
            noWrap
            sx={{
              position: "absolute", left: 0, right: 0, bottom: 0, px: 1, py: 0.5,
              bgcolor: "rgba(0,0,0,.55)", color: "#fff",
            }}
          >
            {label} · {file.name}
          </Typography>
          {!disabled && (
            <Tooltip title="Remove">
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onChange(null);
                }}
                sx={{ position: "absolute", top: 4, right: 4, bgcolor: "rgba(0,0,0,.55)", color: "#fff", "&:hover": { bgcolor: "rgba(0,0,0,.75)" } }}
              >
                <CloseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </>
      )}
    </Box>
  );
}
