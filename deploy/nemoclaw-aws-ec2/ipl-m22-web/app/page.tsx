"use client";

import { useCallback, useState } from "react";

const ANALYZE_MUTATION = `
mutation Analyze(
  $img: String!
  $goal: TreatmentGoalGQL!
  $notes: String
  $fp: Int
  $hair: HairColorGQL
) {
  analyzeAndRecommend(
    imageBase64: $img
    treatmentGoal: $goal
    clinicalNotes: $notes
    overrideFitzpatrick: $fp
    overrideHairColor: $hair
  ) {
    analysis {
      suggestedFitzpatrick
      fitzpatrickConfidence
      suggestedHairColor
      hairConfidence
      analysisWarnings
    }
    recommendation {
      consultationId
      filterHint
      energyJCm2
      pulseMs
      spotSizeMm
      coolingLevelHint
      warnings
      rationale
    }
  }
}
`;

type GqlResponse = {
  data?: unknown;
  errors?: { message: string }[];
};

function fileToBase64DataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(file);
  });
}

export default function Page() {
  const [goal, setGoal] = useState("HAIR_REMOVAL");
  const [notes, setNotes] = useState("");
  const [overrideFp, setOverrideFp] = useState("");
  const [overrideHair, setOverrideHair] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GqlResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(
    async (file: File | null) => {
      setErr(null);
      setResult(null);
      if (!file) {
        setErr("Elige una imagen (JPG/PNG).");
        return;
      }
      setLoading(true);
      try {
        const img = await fileToBase64DataUrl(file);
        const variables: Record<string, unknown> = {
          img,
          goal,
        };
        if (notes.trim()) variables.notes = notes.trim();
        const fp = parseInt(overrideFp, 10);
        if (!Number.isNaN(fp) && fp >= 1 && fp <= 6) variables.fp = fp;
        if (overrideHair.trim()) variables.hair = overrideHair.trim();

        const res = await fetch("/api/graphql", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: ANALYZE_MUTATION,
            variables,
          }),
        });
        const json = (await res.json()) as GqlResponse;
        if (!res.ok && !json.errors) {
          setErr(`HTTP ${res.status}`);
          return;
        }
        setResult(json);
        if (json.errors?.length) {
          setErr(json.errors.map((e) => e.message).join("\n"));
        }
      } catch (e) {
        setErr(e instanceof Error ? e.message : "Error");
      } finally {
        setLoading(false);
      }
    },
    [goal, notes, overrideFp, overrideHair]
  );

  return (
    <>
      <h1>IPL M22 — análisis + recomendación</h1>
      <p className="note">
        El navegador llama a <code>/api/graphql</code> en Vercel (HTTPS); el servidor reenvía a tu EC2.
        Configura <code>IPL_GRAPHQL_BACKEND</code> en Vercel (URL del GraphQL en la instancia).
      </p>

      <label>Foto del área (retrato / piel + pelo)</label>
      <input
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(e) => run(e.target.files?.[0] ?? null)}
        disabled={loading}
      />

      <label>Objetivo del tratamiento</label>
      <select value={goal} onChange={(e) => setGoal(e.target.value)} disabled={loading}>
        <option value="HAIR_REMOVAL">Depilación (HR)</option>
        <option value="PHOTOREJUVENATION">Foto rejuvenecimiento</option>
        <option value="PIGMENT">Pigmento</option>
        <option value="VASCULAR">Vascular</option>
      </select>

      <label>Notas clínicas (opcional)</label>
      <input
        type="text"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Paciente, zona, etc."
        disabled={loading}
        style={{ width: "100%", padding: "0.5rem", borderRadius: 6, border: "1px solid #2f3336", background: "#16181c", color: "#e7e9ea" }}
      />

      <label>Override Fitzpatrick 1–6 (opcional)</label>
      <input
        type="number"
        min={1}
        max={6}
        value={overrideFp}
        onChange={(e) => setOverrideFp(e.target.value)}
        disabled={loading}
        style={{ width: "6rem", padding: "0.5rem", borderRadius: 6, border: "1px solid #2f3336", background: "#16181c", color: "#e7e9ea" }}
      />

      <label>Override color pelo (opcional, enum)</label>
      <select
        value={overrideHair}
        onChange={(e) => setOverrideHair(e.target.value)}
        disabled={loading}
        style={{ display: "block", padding: "0.5rem", borderRadius: 6 }}
      >
        <option value="">— automático —</option>
        <option value="BLONDE">BLONDE</option>
        <option value="RED">RED</option>
        <option value="LIGHT_BROWN">LIGHT_BROWN</option>
        <option value="BROWN">BROWN</option>
        <option value="BLACK">BLACK</option>
        <option value="GRAY_WHITE">GRAY_WHITE</option>
        <option value="UNKNOWN">UNKNOWN</option>
      </select>

      {err && <p className="error">{err}</p>}
      {loading && <p>Enviando…</p>}
      {result && (
        <pre>{JSON.stringify(result.data ?? result, null, 2)}</pre>
      )}

      <p className="note" style={{ marginTop: "2rem" }}>
        Uso educativo. No sustituye manual del equipo ni criterio médico.
      </p>
    </>
  );
}
