"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { getCV, setCV, getLatexTemplate, setLatexTemplate } from "@/lib/cv";

export default function CVPage() {
  const [cv, setCVState] = useState("");
  const [tmpl, setTmplState] = useState("");
  const [saved, setSaved] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parseInfo, setParseInfo] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setCVState(getCV());
    setTmplState(getLatexTemplate());
  }, []);

  function handleSave() {
    setCV(cv);
    setLatexTemplate(tmpl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setParseError(null);
    setParseInfo(null);
    setParsing(true);
    try {
      const { text, pages } = await api.parseCv(file);
      setCVState(text);
      setParseInfo(`Parsed ${pages} page${pages === 1 ? "" : "s"} from ${file.name} — review and edit below, then Save.`);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err));
    } finally {
      setParsing(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Your CV</h1>
        <p className="mt-1 text-sm text-neutral-600">
          Upload a PDF or paste plain text. Saved locally in your browser — never sent anywhere except to your own backend during applications.
        </p>
      </div>

      <div className="rounded-lg border border-neutral-200 bg-white p-4 space-y-3">
        <div>
          <label className="block text-sm font-medium mb-2">Upload CV (PDF or .txt)</label>
          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,application/pdf,text/plain"
              onChange={handleFile}
              disabled={parsing}
              className="block text-sm file:mr-3 file:rounded-md file:border-0 file:bg-neutral-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-neutral-800 file:cursor-pointer file:disabled:opacity-50"
            />
            {parsing && <span className="text-sm text-neutral-600">Parsing...</span>}
          </div>
        </div>
        {parseInfo && (
          <p className="text-xs text-emerald-700">{parseInfo}</p>
        )}
        {parseError && (
          <p className="text-xs text-rose-700">{parseError}</p>
        )}
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium">CV text</label>
        <textarea
          value={cv}
          onChange={(e) => setCVState(e.target.value)}
          rows={20}
          placeholder="Paste your full CV here, or upload a PDF above..."
          className="w-full rounded-md border border-neutral-300 bg-white p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-neutral-900"
        />
        <p className="text-xs text-neutral-500">{cv.length} characters</p>
      </div>

      <div className="space-y-2">
        <label className="block text-sm font-medium">
          LaTeX template <span className="text-neutral-500 font-normal">(optional — paste your Overleaf .tex)</span>
        </label>
        <textarea
          value={tmpl}
          onChange={(e) => setTmplState(e.target.value)}
          rows={12}
          placeholder="\documentclass{article}..."
          className="w-full rounded-md border border-neutral-300 bg-white p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-neutral-900"
        />
        <p className="text-xs text-neutral-500">
          If provided, the crew fills your tailored CV into this template and produces a PDF.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
        >
          Save
        </button>
        {saved && <span className="text-sm text-emerald-700">Saved.</span>}
      </div>
    </div>
  );
}
