// Lecture Brain — embeds the lecturepdfs corpus's own UI via the gated same-origin
// reverse-proxy `/api/corpus/gnocr/serve/` (plan T3.2).
//
// Ruling F1 (BINDING): NO `sandbox` attribute. This is the owner's own trusted
// local corpus served from SAMAGRA's own origin-gated origin; a sandbox would
// force an opaque origin and break every same-origin fetch the embedded app
// makes. The Pratham published-artifact iframe keeps its sandbox — untouched,
// different threat model (untrusted public-by-design bytes that fetch nothing).
import { useCallback, useEffect, useState } from "react";

const NAME = "lecturepdf";
const TITLE = "Lecture Brain";
const PORT = 8000;
const SERVE = `/api/corpus/${NAME}/serve/`;
const STATUS = `/api/corpus/${NAME}`;

type Probe = "probing" | "online" | "offline";

export default function LectureBrain() {
  const [probe, setProbe] = useState<Probe>("probing");
  const check = useCallback(() => {
    setProbe("probing");
    fetch(STATUS)
      .then((r) => setProbe(r.ok ? "online" : "offline"))
      .catch(() => setProbe("offline"));
  }, []);
  useEffect(() => {
    check();
  }, [check]);

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%" }}>
      {probe === "offline" ? (
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            color: "var(--samagra-text)",
            background: "var(--samagra-panel, transparent)",
            textAlign: "center",
            padding: 24,
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 600 }}>brain offline</div>
          <div style={{ fontSize: 12.5, opacity: 0.75 }}>
            start the sidecar :{PORT} then retry
          </div>
          <button
            onClick={check}
            style={{
              marginTop: 6,
              padding: "6px 18px",
              borderRadius: 7,
              border: "1px solid var(--samagra-border, #8884)",
              background: "var(--samagra-accent, #4f46e5)",
              color: "#fff",
              cursor: "pointer",
              font: "inherit",
            }}
          >
            Retry
          </button>
        </div>
      ) : (
        <iframe
          title={TITLE}
          src={SERVE}
          referrerPolicy="no-referrer"
          style={{ flex: 1, width: "100%", height: "100%", border: 0, background: "#fff" }}
        />
      )}
    </div>
  );
}
