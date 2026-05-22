// CV is stored in localStorage so it persists across pages without a backend user/auth model.

const CV_KEY = "job_applier_cv";
const TEMPLATE_KEY = "job_applier_latex_template";

export function getCV(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(CV_KEY) || "";
}

export function setCV(cv: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(CV_KEY, cv);
}

export function getLatexTemplate(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TEMPLATE_KEY) || "";
}

export function setLatexTemplate(t: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TEMPLATE_KEY, t);
}
