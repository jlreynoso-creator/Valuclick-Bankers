import type { Context } from "@netlify/functions";
import { eq } from "drizzle-orm";
import db from "../../db/index.js";
import { users } from "../../db/schema.js";
import {
  hashPassword,
  createAccessToken,
  jsonResponse,
  errorResponse,
} from "./utils/auth.mjs";

export default async function handler(request: Request, _context: Context) {
  if (request.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  let body: { email?: string; password?: string; full_name?: string };
  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON body");
  }

  const { email, password, full_name } = body;
  if (!email || !password || !full_name) {
    return errorResponse("Email, password y nombre son requeridos");
  }

  const existing = await db
    .select()
    .from(users)
    .where(eq(users.email, email))
    .limit(1);

  if (existing.length > 0) {
    return errorResponse("Email ya registrado", 400);
  }

  const hashedPwd = await hashPassword(password);

  const [user] = await db
    .insert(users)
    .values({
      email,
      fullName: full_name,
      hashedPassword: hashedPwd,
      oauthProvider: "email",
      subscriptionPlan: "free",
    })
    .returning();

  const accessToken = await createAccessToken(user.id, user.email);

  return jsonResponse({
    access_token: accessToken,
    token_type: "bearer",
    user_id: user.id,
    email: user.email,
  });
}

export const config = {
  path: "/api/auth/register",
  method: "POST",
};
