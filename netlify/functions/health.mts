import type { Context } from "@netlify/functions";
import { jsonResponse } from "./utils/auth.mjs";

export default async function handler(_request: Request, _context: Context) {
  return jsonResponse({ status: "ok", version: "1.0.0" });
}

export const config = {
  path: "/health",
};
